/**
 * Screen Change Detector Service
 *
 * Detects screen content changes using lightweight screenshots and
 * perceptual image hashing. Triggers callbacks when significant
 * visual changes are detected.
 *
 * Used to automatically update halo position when user scrolls
 * or interacts with the target application.
 */

import { captureScreenLowRes, captureWindow, captureWindowByHwnd } from '../api/detection';

// =============================================
// Types
// =============================================

export interface ChangeDetectorConfig {
  /** Polling interval for change detection (ms) */
  pollIntervalMs: number;
  /** Debounce time after changes stop before triggering callback (ms) */
  debounceMs: number;
  /** Resolution for change detection screenshots */
  detectWidth: number;
  detectHeight: number;
  /** Hash difference threshold (0-1) to consider as "changed" */
  changeThreshold: number;
}

export type ChangeCallback = () => void;

// =============================================
// Perceptual Hash Implementation
// =============================================

/**
 * Computes a simple perceptual hash from a base64 image.
 *
 * Uses average hash algorithm (aHash):
 * 1. Resize to small grid (we use the low-res capture)
 * 2. Convert to grayscale
 * 3. Compute average brightness
 * 4. Create binary hash based on above/below average
 *
 * This is computed from raw pixel data extracted via ImageData.
 * For simplicity, we'll compute a checksum-based hash from the base64 string
 * which is less accurate but much faster without canvas operations.
 */
function computeSimpleHash(base64Image: string): string {
  // Use a simple but effective approach: sample bytes from the base64 string
  // This detects changes in image content efficiently
  const sampleSize = 256;
  const step = Math.max(1, Math.floor(base64Image.length / sampleSize));

  let hash = '';
  for (let i = 0; i < base64Image.length && hash.length < sampleSize; i += step) {
    hash += base64Image.charAt(i);
  }

  return hash;
}

/**
 * Computes Hamming distance ratio between two hash strings.
 *
 * @returns A value between 0 (identical) and 1 (completely different)
 */
function computeHashDifference(hash1: string, hash2: string): number {
  if (!hash1 || !hash2) return 1.0;
  if (hash1.length !== hash2.length) return 1.0;

  let differences = 0;
  for (let i = 0; i < hash1.length; i++) {
    if (hash1[i] !== hash2[i]) {
      differences++;
    }
  }

  return differences / hash1.length;
}

// =============================================
// Screen Change Detector Class
// =============================================

class ScreenChangeDetector {
  private config: ChangeDetectorConfig;
  private isRunning = false;
  private pollIntervalId: ReturnType<typeof setInterval> | null = null;
  private debounceTimeoutId: ReturnType<typeof setTimeout> | null = null;
  private previousHash: string | null = null;
  private changeCallback: ChangeCallback | null = null;
  private targetWindowPattern: string | null = null;
  private targetHwnd: number | null = null;  // HWND for URL-based matching
  private isChangeInProgress = false;
  private lastChangeTime = 0;
  private changeCount = 0;

  constructor(config?: Partial<ChangeDetectorConfig>) {
    this.config = {
      pollIntervalMs: 100,      // Check for changes every 100ms
      debounceMs: 1000,         // Wait 1000ms (1s) after changes stop for screen stability
      detectWidth: 160,         // Very low res for speed
      detectHeight: 120,
      changeThreshold: 0.15,    // 15% difference triggers change (higher to ignore clock/cursor/animations)
      ...config,
    };
  }

  /**
   * Start monitoring for screen changes.
   *
   * @param callback Called when screen changes are detected (after debounce)
   * @param targetPattern Optional window title pattern to capture
   * @param targetHwnd Optional HWND for URL-based matching (takes priority over pattern)
   */
  start(callback: ChangeCallback, targetPattern?: string, targetHwnd?: number): void {
    if (this.isRunning) {
      console.log('[ScreenChangeDetector] Already running');
      return;
    }

    this.changeCallback = callback;
    this.targetWindowPattern = targetPattern || null;
    this.targetHwnd = targetHwnd || null;
    this.previousHash = null;
    this.isRunning = true;
    this.changeCount = 0;

    console.log('[ScreenChangeDetector] Starting with config:', {
      pollIntervalMs: this.config.pollIntervalMs,
      debounceMs: this.config.debounceMs,
      targetPattern: this.targetWindowPattern,
      targetHwnd: this.targetHwnd,
    });

    // Start polling loop
    this.pollIntervalId = setInterval(() => {
      this.checkForChanges().catch(console.error);
    }, this.config.pollIntervalMs);
  }

  /**
   * Stop monitoring for screen changes.
   */
  stop(): void {
    if (!this.isRunning) return;

    this.isRunning = false;

    if (this.pollIntervalId) {
      clearInterval(this.pollIntervalId);
      this.pollIntervalId = null;
    }

    if (this.debounceTimeoutId) {
      clearTimeout(this.debounceTimeoutId);
      this.debounceTimeoutId = null;
    }

    this.previousHash = null;
    this.changeCallback = null;
    this.changeCount = 0;

    console.log('[ScreenChangeDetector] Stopped');
  }

  /**
   * Update the target window pattern.
   */
  setTargetPattern(pattern: string | null): void {
    this.targetWindowPattern = pattern;
  }

  /**
   * Update the target HWND for URL-based matching.
   */
  setTargetHwnd(hwnd: number | null): void {
    this.targetHwnd = hwnd;
    console.log('[ScreenChangeDetector] Target HWND updated:', hwnd);
  }

  /**
   * Force a change detection callback (e.g., after step change).
   */
  forceCallback(): void {
    if (this.changeCallback) {
      this.changeCallback();
    }
  }

  /**
   * Reset the baseline hash (force next comparison to pass).
   */
  resetBaseline(): void {
    this.previousHash = null;
  }

  /**
   * Get current detector status.
   */
  getStatus(): { isRunning: boolean; changeCount: number; lastChangeTime: number } {
    return {
      isRunning: this.isRunning,
      changeCount: this.changeCount,
      lastChangeTime: this.lastChangeTime,
    };
  }

  // =============================================
  // Private Methods
  // =============================================

  private async checkForChanges(): Promise<void> {
    if (!this.isRunning || this.isChangeInProgress) return;

    this.isChangeInProgress = true;

    try {
      // Capture low-res screenshot for change detection
      let imageBase64: string | undefined;

      // Priority 1: Use HWND for URL-based matching (most reliable)
      if (this.targetHwnd) {
        try {
          const result = await captureWindowByHwnd(this.targetHwnd);
          if (result.success && result.image_base64) {
            imageBase64 = result.image_base64;
          }
        } catch {
          // Fall back to other methods if HWND capture fails
        }
      }

      // Priority 2: Use window title pattern
      if (!imageBase64 && this.targetWindowPattern) {
        try {
          const result = await captureWindow(this.targetWindowPattern);
          if (result.success && result.image_base64) {
            imageBase64 = result.image_base64;
          }
        } catch {
          // Fall back to screen capture if window capture fails
        }
      }

      // Priority 3: Full screen capture (least reliable)
      if (!imageBase64) {
        const result = await captureScreenLowRes(
          this.config.detectWidth,
          this.config.detectHeight
        );
        if (result.success && result.image_base64) {
          imageBase64 = result.image_base64;
        }
      }

      if (!imageBase64) {
        // Capture failed, skip this cycle
        return;
      }

      // Compute hash of current image
      const currentHash = computeSimpleHash(imageBase64);

      // Compare with previous hash
      if (this.previousHash) {
        const difference = computeHashDifference(this.previousHash, currentHash);

        if (difference > this.config.changeThreshold) {
          // Screen has changed - update debounce timer
          this.handleChange();
        }
      }

      // Update previous hash
      this.previousHash = currentHash;

    } catch (error) {
      // Silently handle errors to avoid spamming console
      // Change detection is best-effort
    } finally {
      this.isChangeInProgress = false;
    }
  }

  private handleChange(): void {
    this.changeCount++;
    this.lastChangeTime = Date.now();

    // Clear existing debounce timer
    if (this.debounceTimeoutId) {
      clearTimeout(this.debounceTimeoutId);
    }

    // Set new debounce timer
    this.debounceTimeoutId = setTimeout(() => {
      this.debounceTimeoutId = null;

      // Fire callback after debounce period with no new changes
      if (this.changeCallback && this.isRunning) {
        console.log('[ScreenChangeDetector] Change detected, triggering callback');
        this.changeCallback();
      }
    }, this.config.debounceMs);
  }
}

// =============================================
// Singleton Instance
// =============================================

let detectorInstance: ScreenChangeDetector | null = null;

/**
 * Get the singleton detector instance.
 */
export function getScreenChangeDetector(config?: Partial<ChangeDetectorConfig>): ScreenChangeDetector {
  if (!detectorInstance) {
    detectorInstance = new ScreenChangeDetector(config);
  }
  return detectorInstance;
}

/**
 * Reset the detector (for testing or re-initialization).
 */
export function resetScreenChangeDetector(): void {
  if (detectorInstance) {
    detectorInstance.stop();
    detectorInstance = null;
  }
}

export { ScreenChangeDetector };
export default ScreenChangeDetector;
