/**
 * GuidanceCoordinator Service
 *
 * Orchestrates the automatic guidance flow:
 * 1. Monitors for target application window
 * 2. Captures screen when target app is active
 * 3. Analyzes screen with CV pipeline
 * 4. Matches detected elements to current guidance step
 * 5. Shows/updates halo overlay
 */

import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import {
  startWindowMonitoring,
  stopWindowMonitoring,
  isWindowMonitoringActive,
  captureScreen,
  captureWindow,
  smartMatchWindow,
  getForegroundWindowSimple,
  type SmartMatchConfig,
  type ForegroundWindowInfo,
} from '../api/detection';
import { getScreenChangeDetector, type ScreenChangeDetector } from './ScreenChangeDetector';
import type { WindowMatchEvent } from '../types/detection';
import {
  createOverlayWindow,
  destroyOverlayWindow,
  showGuidanceStepHalo,
  updateGuidanceStepHalo,
  hideHalo,
  isOverlayCreated,
} from '../api/halo';
import {
  showGuidancePanel,
  updateGuidancePanel,
  closeGuidancePanel,
  notifyPanelCoordinatorStatus,
  setSidePanelTargetPattern,
  isSidePanelCreated,
} from '../api/sidepanel';
import { getTargetAppSettings, getTargetApp, captureStep, fastPositionUpdate, detectBrowserWithUrl, type FastPositionUpdateResponse, type BrowserUrlResponse } from '../api/guidance';
import type {
  GuidanceSession,
  GuidanceStep,
  HaloTarget,
  TargetAppSettings,
  CaptureStepResponse,
  TargetApplication,
  TimingBreakdown,
} from '../types/guidance';
import type { WindowPattern } from '../types/detection';
import type { BoundingBox } from '../overlay/types';

// =============================================
// Types
// =============================================

export type CoordinatorStatus =
  | 'idle'
  | 'initializing'
  | 'monitoring'
  | 'target_found'
  | 'capturing'
  | 'analyzing'
  | 'showing_halo'
  | 'waiting_action'
  | 'paused'
  | 'error';

export interface CoordinatorState {
  status: CoordinatorStatus;
  session: GuidanceSession | null;
  currentStep: GuidanceStep | null;
  currentTarget: HaloTarget | null;
  targetAppSettings: TargetAppSettings | null;
  isTargetWindowActive: boolean;
  error: string | null;
  lastUpdateTime: number;
  /** Cached HWND of matched browser window (for URL-based matching) */
  matchedBrowserHwnd: number | null;
  /** Timing breakdown from last CV analysis */
  lastTiming: TimingBreakdown | null;
}

export interface CoordinatorConfig {
  captureIntervalMs: number;
  windowPollIntervalMs: number;
  autoStartOnTargetWindow: boolean;
  showHaloOnStepChange: boolean;
  /** Use screen change detection instead of fixed interval */
  useChangeDetection: boolean;
  /** Polling interval for change detection (ms) */
  changeDetectionPollMs: number;
  /** Debounce time after changes stop (ms) */
  changeDetectionDebounceMs: number;
}

export type CoordinatorEventType =
  | 'status_changed'
  | 'target_window_found'
  | 'target_window_lost'
  | 'step_target_found'
  | 'step_completed'
  | 'session_completed'
  | 'error';

export interface CoordinatorEvent {
  type: CoordinatorEventType;
  data: unknown;
  timestamp: number;
}

type EventCallback = (event: CoordinatorEvent) => void;

// =============================================
// GuidanceCoordinator Class
// =============================================

class GuidanceCoordinator {
  private state: CoordinatorState;
  private config: CoordinatorConfig;
  private eventListeners: Map<CoordinatorEventType, Set<EventCallback>>;
  private windowMonitorUnlisten: UnlistenFn | null = null;
  private panelReadyUnlisten: UnlistenFn | null = null;
  private panelNavUnlisteners: UnlistenFn[] = [];
  private captureIntervalId: ReturnType<typeof setInterval> | null = null;
  private isDestroyed = false;
  private allSteps: GuidanceStep[] = [];
  private pendingStatusUpdate: Promise<unknown> | null = null;
  private statusUpdateVersion = 0;
  private isCaptureInProgress = false; // Mutex to prevent concurrent captures
  private screenChangeDetector: ScreenChangeDetector | null = null;
  private verifiedHwnds: Set<number> = new Set(); // HWNDs verified via URL/process matching
  private fastVerifyIntervalId: ReturnType<typeof setInterval> | null = null; // Fast verification monitor
  private lastFullCvTime: number = 0; // Throttle full CV analysis
  private readonly FULL_CV_THROTTLE_MS = 30000; // Only run full CV every 30 seconds max
  private urlVerificationFailureCount: number = 0; // Consecutive URL verification failures
  private readonly URL_VERIFICATION_FAILURE_THRESHOLD = 3; // Hide halo only after N consecutive failures

  // Callback for external step advancement (set by useGuidanceCoordinator)
  public onPanelNextClicked: (() => Promise<void>) | null = null;
  public onPanelPrevClicked: (() => Promise<void>) | null = null;
  public onPanelSkipClicked: (() => Promise<void>) | null = null;
  public onPanelEndSession: (() => Promise<void>) | null = null;

  constructor(config?: Partial<CoordinatorConfig>) {
    this.config = {
      captureIntervalMs: 2000, // Capture every 2 seconds (fallback)
      windowPollIntervalMs: 500, // Check window every 500ms
      autoStartOnTargetWindow: true,
      showHaloOnStepChange: true,
      useChangeDetection: true, // Use smart change detection by default
      changeDetectionPollMs: 100, // Check for changes every 100ms
      changeDetectionDebounceMs: 400, // Wait 400ms after changes stop
      ...config,
    };

    this.state = {
      status: 'idle',
      session: null,
      currentStep: null,
      currentTarget: null,
      targetAppSettings: null,
      isTargetWindowActive: false,
      error: null,
      lastUpdateTime: Date.now(),
      matchedBrowserHwnd: null,
      lastTiming: null,
    };

    this.eventListeners = new Map();
  }

  // =============================================
  // Public API
  // =============================================

  /**
   * Get current coordinator state
   */
  getState(): CoordinatorState {
    return { ...this.state };
  }

  /**
   * Get current status
   */
  getStatus(): CoordinatorStatus {
    return this.state.status;
  }

  /**
   * Subscribe to coordinator events
   */
  on(eventType: CoordinatorEventType, callback: EventCallback): () => void {
    if (!this.eventListeners.has(eventType)) {
      this.eventListeners.set(eventType, new Set());
    }
    this.eventListeners.get(eventType)!.add(callback);

    // Return unsubscribe function
    return () => {
      this.eventListeners.get(eventType)?.delete(callback);
    };
  }

  /**
   * Initialize the coordinator with a guidance session
   * @param session - The guidance session
   * @param steps - Array of guidance steps
   * @param appId - Optional target application ID. If provided, loads that specific app's settings.
   *                If not provided, loads the default target app settings.
   */
  async initialize(session: GuidanceSession, steps: GuidanceStep[], appId?: string): Promise<void> {
    if (this.isDestroyed) {
      throw new Error('Coordinator has been destroyed');
    }

    this.updateStatus('initializing');

    try {
      // Store session info and all steps for later lookup
      this.state.session = session;
      this.allSteps = steps;
      this.state.currentStep = steps.find(s => s.step_number === session.current_step) || steps[0];

      // Load target app settings (specific app if appId provided, otherwise default)
      await this.loadTargetAppSettings(appId);

      // Create overlay window
      const overlayExists = await isOverlayCreated();
      if (!overlayExists) {
        await createOverlayWindow();
      }

      // Listen for panel ready event to re-sync session state
      // This handles the race condition where panel might not be ready when events are first sent
      this.panelReadyUnlisten = await listen('panel:ready', async () => {
        console.log('[GuidanceCoordinator] Panel ready event received, syncing session state');
        if (this.state.session) {
          // Re-send session info
          await showGuidancePanel(
            this.state.session.session_id,
            this.state.session.query,
            this.state.session.total_steps,
            this.state.session.application_context || null
          );
          // Re-send current step
          if (this.state.currentStep) {
            await this.updateSidePanel(this.state.currentStep);
          }
          // Re-send status
          await this.updatePanelStatus();
        }
      });

      // Listen for panel navigation events
      this.panelNavUnlisteners = [];

      // Next button clicked
      const nextUnlisten = await listen('panel:next_clicked', async () => {
        console.log('[GuidanceCoordinator] Panel next clicked');
        if (this.onPanelNextClicked) {
          await this.onPanelNextClicked();
        }
      });
      this.panelNavUnlisteners.push(nextUnlisten);

      // Previous button clicked
      const prevUnlisten = await listen('panel:prev_clicked', async () => {
        console.log('[GuidanceCoordinator] Panel prev clicked');
        if (this.onPanelPrevClicked) {
          await this.onPanelPrevClicked();
        }
      });
      this.panelNavUnlisteners.push(prevUnlisten);

      // Skip button clicked
      const skipUnlisten = await listen('panel:skip_clicked', async () => {
        console.log('[GuidanceCoordinator] Panel skip clicked');
        if (this.onPanelSkipClicked) {
          await this.onPanelSkipClicked();
        }
      });
      this.panelNavUnlisteners.push(skipUnlisten);

      // End session clicked
      const endUnlisten = await listen('panel:end_session', async () => {
        console.log('[GuidanceCoordinator] Panel end session clicked');
        if (this.onPanelEndSession) {
          await this.onPanelEndSession();
        }
      });
      this.panelNavUnlisteners.push(endUnlisten);

      // Show the side panel with session info
      await showGuidancePanel(
        session.session_id,
        session.query,
        session.total_steps,
        session.application_context || null
      );

      // Set target pattern for auto-minimize
      if (this.state.targetAppSettings?.target_window_pattern) {
        await setSidePanelTargetPattern(this.state.targetAppSettings.target_window_pattern);
      }

      // Update panel with current step (with a small delay to allow panel to mount)
      if (this.state.currentStep) {
        // Small delay to ensure panel is ready
        setTimeout(async () => {
          if (this.state.currentStep) {
            await this.updateSidePanel(this.state.currentStep);
          }
        }, 500);
      }

      // Start window monitoring if target app is configured
      if (this.state.targetAppSettings?.is_configured) {
        await this.startWindowMonitoring();
      }

      this.updateStatus('monitoring');
      console.log('GuidanceCoordinator initialized successfully');
    } catch (error) {
      this.handleError('Initialization failed', error);
    }
  }

  /**
   * Start active guidance (begin capture loop)
   */
  async startActiveGuidance(): Promise<void> {
    if (this.state.status === 'error' || this.state.status === 'idle') {
      throw new Error('Coordinator not properly initialized');
    }

    this.startCaptureLoop();
    this.updateStatus('capturing');
  }

  /**
   * Pause the guidance (stop capture loop but maintain state)
   */
  pause(): void {
    this.stopCaptureLoop();
    this.updateStatus('paused');
  }

  /**
   * Resume the guidance
   */
  resume(): void {
    if (this.state.status !== 'paused') return;
    this.startCaptureLoop();
    this.updateStatus('capturing');
  }

  /**
   * Move to next step
   */
  async nextStep(): Promise<void> {
    if (!this.state.session || !this.state.currentStep) return;

    const nextStepNumber = this.state.currentStep.step_number + 1;
    if (nextStepNumber > this.state.session.total_steps) {
      this.emitEvent('session_completed', { session: this.state.session });
      return;
    }

    // Update step via backend
    // The actual step transition logic would go here
    // For now, trigger a capture to find the new target
    await this.captureAndMatchTarget();
  }

  /**
   * Skip current step
   */
  async skipStep(): Promise<void> {
    await this.nextStep();
  }

  /**
   * Update the current step (called when store step changes externally)
   * This syncs the coordinator with the Zustand store
   */
  updateCurrentStep(stepNumber: number): void {
    if (!this.state.session) return;

    const newStep = this.allSteps.find(s => s.step_number === stepNumber);
    if (newStep) {
      console.log('[GuidanceCoordinator] Updating current step to:', stepNumber);
      this.state.currentStep = newStep;
      this.state.currentTarget = null; // Clear target for new step

      // Update the side panel with new step
      this.updateSidePanel(newStep).catch(console.error);

      // Reset change detector baseline so next comparison triggers capture
      if (this.screenChangeDetector) {
        this.screenChangeDetector.resetBaseline();
      }

      // Reset throttle timer - step change should trigger immediate full CV
      this.lastFullCvTime = 0;

      // Trigger immediate capture for new step if we're actively capturing
      if (['capturing', 'showing_halo', 'waiting_action'].includes(this.state.status)) {
        this.captureAndMatchTarget().catch(console.error);
      }
    }
  }

  /**
   * Update the side panel with current step info
   */
  private async updateSidePanel(step: GuidanceStep): Promise<void> {
    const panelCreated = await isSidePanelCreated();
    if (!panelCreated) return;

    await updateGuidancePanel(
      step.step_number,
      this.state.session?.total_steps || step.step_number,
      step.instruction,
      step.detailed_instruction || null,
      step.action_type || 'click',
      step.target?.label || null,
      this.state.currentTarget?.confidence || null,
      this.state.lastTiming
    );
  }

  /**
   * Update the side panel coordinator status
   * Uses versioning to ensure only the latest status is sent
   */
  private async updatePanelStatus(): Promise<void> {
    // Increment version and capture it for this update
    this.statusUpdateVersion++;
    const myVersion = this.statusUpdateVersion;

    // Capture current status before any async operations
    const currentStatus = this.state.status;
    const isTargetActive = this.state.isTargetWindowActive;
    const targetPattern = this.state.targetAppSettings?.target_window_pattern || null;

    // Wait for any pending update to complete
    if (this.pendingStatusUpdate) {
      await this.pendingStatusUpdate;
    }

    // Check if a newer update was requested while we waited
    if (myVersion !== this.statusUpdateVersion) {
      return; // Skip this update, a newer one is coming
    }

    // Check if panel exists
    const panelCreated = await isSidePanelCreated();
    if (!panelCreated) return;

    // Check again after async call
    if (myVersion !== this.statusUpdateVersion) {
      return;
    }

    const statusMap: Record<CoordinatorStatus, string> = {
      idle: 'idle',
      initializing: 'waiting',
      monitoring: 'waiting',
      target_found: 'tracking',
      capturing: 'scanning',
      analyzing: 'scanning',
      showing_halo: 'tracking',
      waiting_action: 'tracking',
      paused: 'waiting',
      error: 'error',
    };

    // Create and track this update
    this.pendingStatusUpdate = notifyPanelCoordinatorStatus(
      statusMap[currentStatus],
      isTargetActive,
      targetPattern
    );

    await this.pendingStatusUpdate;
    this.pendingStatusUpdate = null;
  }

  /**
   * Update session info (for sync with store)
   */
  updateSession(session: GuidanceSession): void {
    this.state.session = session;
  }

  /**
   * Stop guidance and cleanup
   */
  async stop(): Promise<void> {
    this.stopCaptureLoop();
    await this.stopWindowMonitoring();
    await hideHalo();

    // Stop listening for panel ready events
    if (this.panelReadyUnlisten) {
      this.panelReadyUnlisten();
      this.panelReadyUnlisten = null;
    }

    // Stop listening for panel navigation events
    this.panelNavUnlisteners.forEach(unlisten => unlisten());
    this.panelNavUnlisteners = [];

    // Close the side panel
    await closeGuidancePanel('abandoned');

    this.updateStatus('idle');
    this.state.session = null;
    this.state.currentStep = null;
    this.state.currentTarget = null;
  }

  /**
   * Destroy the coordinator and cleanup all resources
   */
  async destroy(): Promise<void> {
    this.isDestroyed = true;
    await this.stop();
    await destroyOverlayWindow();
    this.eventListeners.clear();

    // Ensure panel ready listener is cleaned up
    if (this.panelReadyUnlisten) {
      this.panelReadyUnlisten();
      this.panelReadyUnlisten = null;
    }

    // Ensure panel navigation listeners are cleaned up
    this.panelNavUnlisteners.forEach(unlisten => unlisten());
    this.panelNavUnlisteners = [];
  }

  // =============================================
  // Window Monitoring
  // =============================================

  /**
   * Load target application settings.
   * @param appId - Optional specific app ID. If provided, loads that app's settings.
   *                If not provided, loads the default target app settings.
   */
  private async loadTargetAppSettings(appId?: string): Promise<void> {
    try {
      if (appId) {
        // Load specific target app by ID
        console.log('[GuidanceCoordinator] Loading specific target app:', appId);
        const targetApp = await getTargetApp(appId);

        // Convert TargetApplication to TargetAppSettings format
        this.state.targetAppSettings = this.convertToTargetAppSettings(targetApp);
        console.log('[GuidanceCoordinator] Loaded target app settings:', this.state.targetAppSettings);
      } else {
        // Load default target app settings (legacy behavior)
        console.log('[GuidanceCoordinator] Loading default target app settings');
        const settings = await getTargetAppSettings();
        console.log('[GuidanceCoordinator] Received target app settings:', settings);
        console.log('[GuidanceCoordinator] Brand keywords:', settings?.target_brand_keywords);
        this.state.targetAppSettings = settings;
      }
    } catch (error) {
      console.warn('Could not load target app settings:', error);
      this.state.targetAppSettings = null;
    }
  }

  /**
   * Convert a TargetApplication response to TargetAppSettings format.
   * This bridges the new multi-app model with the existing coordinator logic.
   */
  private convertToTargetAppSettings(app: TargetApplication): TargetAppSettings {
    return {
      org_id: app.org_id,
      target_app_name: app.app_name,
      target_window_pattern: app.window_pattern,
      target_process_name: app.process_name,
      target_window_class: app.window_class,
      target_app_config: app.app_config,
      target_match_mode: app.match_mode,
      target_url_pattern: app.url_pattern,
      target_url_patterns: app.url_patterns,
      target_brand_keywords: app.brand_keywords,
      is_configured: app.is_configured,
    };
  }

  private async startWindowMonitoring(): Promise<void> {
    if (!this.state.targetAppSettings?.target_window_pattern) {
      console.log('No target window pattern configured, skipping window monitoring');
      return;
    }

    // Strip wildcard characters from pattern for contains matching
    const cleanPattern = this.state.targetAppSettings.target_window_pattern
      .replace(/\*/g, '')
      .trim();

    const patterns: WindowPattern[] = [
      {
        pattern: cleanPattern,
        mode: 'contains',
        case_sensitive: false,
      },
    ];

    // Listen for window match events
    this.windowMonitorUnlisten = await listen<WindowMatchEvent>(
      'window-match',
      (event) => this.handleWindowMatch(event.payload)
    );

    // Start monitoring
    await startWindowMonitoring({
      patterns,
      poll_interval_ms: this.config.windowPollIntervalMs,
    });

    console.log('Window monitoring started for pattern:', cleanPattern);
  }

  private async stopWindowMonitoring(): Promise<void> {
    if (this.windowMonitorUnlisten) {
      this.windowMonitorUnlisten();
      this.windowMonitorUnlisten = null;
    }

    try {
      const isActive = await isWindowMonitoringActive();
      if (isActive) {
        await stopWindowMonitoring();
      }
    } catch {
      // Ignore errors when stopping
    }
  }

  private handleWindowMatch(event: WindowMatchEvent): void {
    console.log('Window match:', event);

    const wasActive = this.state.isTargetWindowActive;
    this.state.isTargetWindowActive = true;

    if (!wasActive) {
      this.emitEvent('target_window_found', {
        windowTitle: event.window_info.title
      });

      // Auto-start capture if configured
      if (this.config.autoStartOnTargetWindow &&
          this.state.status === 'monitoring') {
        this.startCaptureLoop();
        this.updateStatus('capturing');
      }
    }
  }

  // =============================================
  // Screen Capture Loop
  // =============================================

  private startCaptureLoop(): void {
    // Start fast verification monitor (runs independently, checks every 3 seconds)
    this.startFastVerificationMonitor();

    // Use change detection mode if enabled
    if (this.config.useChangeDetection) {
      this.startChangeDetectionLoop();
      return;
    }

    // Fallback to fixed interval mode
    if (this.captureIntervalId) return;

    // Initial capture
    this.captureAndMatchTarget().catch(console.error);

    // Setup interval
    this.captureIntervalId = setInterval(() => {
      this.captureAndMatchTarget().catch(console.error);
    }, this.config.captureIntervalMs);

    console.log('Capture loop started (fixed interval mode)');
  }

  /**
   * Start a fast verification monitor that runs independently of full CV.
   * This quickly detects when user navigates away from the target app.
   */
  private startFastVerificationMonitor(): void {
    const hasBrandKeywords = this.state.targetAppSettings?.target_brand_keywords &&
      this.state.targetAppSettings.target_brand_keywords.length > 0;

    if (!hasBrandKeywords) {
      console.log('[FastVerifyMonitor] No brand keywords configured, skipping monitor');
      return;
    }

    if (this.fastVerifyIntervalId) {
      console.log('[FastVerifyMonitor] Already running');
      return;
    }

    console.log('[FastVerifyMonitor] Starting fast verification monitor (every 1s)');

    // Run every 1 second to quickly detect when user leaves target
    // Fast OCR (~500-700ms) makes this responsive without overloading
    this.fastVerifyIntervalId = setInterval(async () => {
      await this.runFastVerificationCheck();
    }, 1000);
  }

  /**
   * Fast update halo position using OCR-only (for scroll handling).
   * Much faster than full CV analysis (~5-10s vs ~50s).
   */
  private async fastUpdateHaloPosition(): Promise<void> {
    if (!this.state.currentTarget?.label || !this.state.session) {
      return;
    }

    // IMPORTANT: Check if user is still on target window before updating
    // This prevents false halo updates when user switches to another window or tab
    const targetPattern = this.state.targetAppSettings?.target_window_pattern;
    const urlPatterns = this.state.targetAppSettings?.target_url_patterns;
    const cachedHwnd = this.state.matchedBrowserHwnd;

    // For URL-based matching with cached HWND, just verify foreground window matches
    // Don't use Rust smartMatchWindow for URL verification - it's unreliable
    // Tab switches will be detected when the Python backend finds the target moved off-screen
    if (cachedHwnd && urlPatterns && urlPatterns.length > 0) {
      try {
        const foregroundWindow = await getForegroundWindowSimple();

        if (!foregroundWindow || foregroundWindow.hwnd !== cachedHwnd) {
          // User switched to a different window - skip this update
          // If they switched tabs (same HWND, different URL), the Python backend
          // will detect that the target element is no longer visible
          console.log('[FastPositionUpdate] Foreground window changed, skipping update');
          return;
        }

        // Foreground matches cached HWND - proceed with position update
        // The Python backend will verify the target is still visible
      } catch (e) {
        console.error('[FastPositionUpdate] Could not check foreground window:', e);
        return;
      }
    } else if (targetPattern) {
      try {
        const foregroundWindow = await getForegroundWindowSimple();
        const cleanPattern = targetPattern.replace(/\*/g, '').trim().toLowerCase();
        const windowTitle = (foregroundWindow?.title || '').toLowerCase();

        if (!windowTitle.includes(cleanPattern)) {
          console.log('[FastPositionUpdate] Not on target window, skipping update');
          return;
        }
      } catch {
        // If we can't check foreground window, skip update to be safe
        console.log('[FastPositionUpdate] Could not verify target window, skipping');
        return;
      }
    }
    let imageBase64: string | undefined;

    try {
      // Priority 1: Use cached browser HWND for URL-based matching
      if (cachedHwnd) {
        const { captureWindowByHwnd } = await import('../api/detection');
        const captureResponse = await captureWindowByHwnd(cachedHwnd);
        if (captureResponse.success && captureResponse.image_base64) {
          imageBase64 = captureResponse.image_base64;
          console.log('[FastPositionUpdate] Captured browser window by HWND');
        }
      }
      // Priority 2: Use title pattern
      else if (targetPattern) {
        const cleanPattern = targetPattern.replace(/\*/g, '').trim();
        const captureResponse = await captureWindow(cleanPattern);
        if (captureResponse.success && captureResponse.image_base64) {
          imageBase64 = captureResponse.image_base64;
        }
      }
      // Priority 3: Full screen fallback (less reliable)
      else {
        console.log('[FastPositionUpdate] No HWND or title pattern, using full screen capture');
        const captureResponse = await captureScreen();
        if (captureResponse.success && captureResponse.image_base64) {
          imageBase64 = captureResponse.image_base64;
        }
      }
    } catch (err) {
      console.error('[FastPositionUpdate] Capture error:', err);
      return;
    }

    if (!imageBase64) {
      return;
    }

    // Get current bbox for proximity matching
    const currentBbox = this.state.currentTarget.bbox ? {
      x1: this.state.currentTarget.bbox.x1,
      y1: this.state.currentTarget.bbox.y1,
      x2: this.state.currentTarget.bbox.x2,
      y2: this.state.currentTarget.bbox.y2,
    } : null;

    try {
      console.log('[FastPositionUpdate] Finding new position for:', this.state.currentTarget.label);
      const startTime = performance.now();

      const result: FastPositionUpdateResponse = await fastPositionUpdate({
        image_base64: imageBase64,
        target_label: this.state.currentTarget.label,
        current_bbox: currentBbox,
        session_id: this.state.session?.session_id,  // Pass session ID for reference tracking
      });

      const endTime = performance.now();
      console.log(
        `[FastPositionUpdate] Completed in ${(endTime - startTime).toFixed(0)}ms, ` +
        `method: ${result.detection_method}, scroll: ${result.scroll_offset_y}px, found: ${result.found}`
      );

      if (result.found && result.new_bbox) {
        // Update halo position
        const bounds: BoundingBox = {
          x: result.new_bbox.x1,
          y: result.new_bbox.y1,
          width: result.new_bbox.x2 - result.new_bbox.x1,
          height: result.new_bbox.y2 - result.new_bbox.y1,
        };

        // Update current target bbox
        this.state.currentTarget.bbox = {
          x1: result.new_bbox.x1,
          y1: result.new_bbox.y1,
          x2: result.new_bbox.x2,
          y2: result.new_bbox.y2,
        };

        console.log('[FastPositionUpdate] Updating halo to new position:', bounds);
        await updateGuidanceStepHalo(
          bounds,
          this.state.currentTarget.step_number,
          this.state.currentTarget.label,
          this.state.currentTarget.target_id,
          this.state.currentStep?.instruction || '',
          this.state.currentTarget.action_type,
          this.state.currentTarget.element_type
        );
      } else {
        // Target not found - might have scrolled off screen
        console.log('[FastPositionUpdate] Target not visible, hiding halo');
        await hideHalo();
      }
    } catch (error) {
      console.error('[FastPositionUpdate] Error:', error);
    }
  }

  /**
   * Run a fast verification check to see if user is still on target app.
   * Uses URL/process matching instead of OCR for reliability.
   * If not on target, immediately hide halo without waiting for full CV.
   */
  private async runFastVerificationCheck(): Promise<void> {
    // Don't run if full CV is in progress (it will handle verification)
    if (this.isCaptureInProgress) {
      return;
    }

    // Get foreground window
    let foregroundWindow: ForegroundWindowInfo | null = null;
    try {
      foregroundWindow = await getForegroundWindowSimple();
    } catch {
      return;
    }

    if (!foregroundWindow) {
      return;
    }

    // IMPORTANT: Skip check if foreground window is our own Pedagogy app
    // This happens when user clicks the side panel (e.g., Next button) during guidance
    // We should NOT hide the halo just because user interacted with our UI
    const processNameLower = foregroundWindow.process_name.toLowerCase();
    const titleLower = foregroundWindow.title.toLowerCase();

    // Debug: log what window is being checked
    console.log('[FastVerifyMonitor] Checking window:', {
      title: foregroundWindow.title,
      process: foregroundWindow.process_name,
      hwnd: foregroundWindow.hwnd,
      isBrowser: foregroundWindow.is_browser,
    });

    if (processNameLower.includes('pedagogy') ||
        titleLower.includes('pedagogy') ||
        titleLower.includes('guidance panel')) {
      // User clicked on our app - this is fine, don't hide halo
      console.log('[FastVerifyMonitor] Skipping - detected Pedagogy app window');
      return;
    }

    // Use smart matching to verify if we're still on target
    // This uses URL/process matching which is more reliable than OCR
    const targetSettings = this.state.targetAppSettings;
    if (!targetSettings) {
      return;
    }

    // Check if it's a browser and we have URL patterns
    const urlPatterns = targetSettings.target_url_patterns;
    const processName = targetSettings.target_process_name;

    let isOnTarget = false;

    // For browsers with URL patterns, check if we have a Python-verified HWND
    // Python's pywinauto is reliable for URL extraction, Rust's uiautomation is not
    if (foregroundWindow.is_browser && urlPatterns && urlPatterns.length > 0) {
      // IMPORTANT: Check for null HWND FIRST to avoid the bug where (number !== null) is always true
      if (!this.state.matchedBrowserHwnd) {
        // No cached HWND yet - wait for Python to verify
        // Don't use Rust verification as it's unreliable
        console.log('[FastVerifyMonitor] No cached browser HWND, waiting for Python verification');
        return; // Skip this check cycle, let Python handle it
      }

      // We have a cached HWND - check if foreground matches
      if (foregroundWindow.hwnd === this.state.matchedBrowserHwnd) {
        // Same browser window that Python verified - trust it
        this.urlVerificationFailureCount = 0;
        isOnTarget = true;
        // Keep the HWND in verified set
        this.verifiedHwnds.add(foregroundWindow.hwnd);
      } else {
        // Different browser window - user switched to another browser window
        // This could be a different tab/window, mark as off-target
        // The next full CV capture will re-verify with Python
        console.log('[FastVerifyMonitor] Foreground browser HWND changed, user may have switched windows');
        isOnTarget = false;

        // Clear cached HWND - will be re-verified by next Python detection
        if (this.verifiedHwnds.has(foregroundWindow.hwnd)) {
          this.verifiedHwnds.delete(foregroundWindow.hwnd);
        }
      }
    }
    // For non-browser windows, we can use HWND caching since the app doesn't change
    else if (this.verifiedHwnds.has(foregroundWindow.hwnd)) {
      // Non-browser HWND already verified, skip further checks
      return;
    }
    // For desktop apps, check process name
    else if (processName) {
      isOnTarget = foregroundWindow.process_name.toLowerCase().includes(processName.toLowerCase());
      if (isOnTarget) {
        this.verifiedHwnds.add(foregroundWindow.hwnd);
      }
    }

    if (!isOnTarget) {
      // User left target app - immediately hide halo
      console.log('[FastVerifyMonitor] User left target app, hiding halo immediately', {
        windowTitle: foregroundWindow.title,
        processName: foregroundWindow.process_name,
        isBrowser: foregroundWindow.is_browser,
        cachedHwnd: this.state.matchedBrowserHwnd,
        foregroundHwnd: foregroundWindow.hwnd,
        urlPatterns: targetSettings?.target_url_patterns,
      });

      if (this.state.isTargetWindowActive) {
        this.state.isTargetWindowActive = false;
        this.emitEvent('target_window_lost', { windowTitle: foregroundWindow?.title || '' });
      }

      this.verifiedHwnds.delete(foregroundWindow.hwnd);

      await hideHalo();
      this.state.currentTarget = null;
    } else if (!this.state.isTargetWindowActive) {
      this.state.isTargetWindowActive = true;
      this.emitEvent('target_window_found', { windowTitle: foregroundWindow?.title || '' });
    }
  }

  /**
   * Start capture loop using screen change detection.
   * Only re-captures when screen content changes (e.g., user scrolls).
   */
  private startChangeDetectionLoop(): void {
    if (this.screenChangeDetector) {
      console.log('[GuidanceCoordinator] Change detection already running');
      return;
    }

    // Get or create the screen change detector
    // Use higher threshold (15%) to ignore clock/cursor/animation changes
    this.screenChangeDetector = getScreenChangeDetector({
      pollIntervalMs: this.config.changeDetectionPollMs,
      debounceMs: this.config.changeDetectionDebounceMs,
      detectWidth: 160,
      detectHeight: 120,
      changeThreshold: 0.15,  // 15% difference to filter out minor changes
    });

    // Get target window pattern for focused capture
    const targetPattern = this.state.targetAppSettings?.target_window_pattern
      ?.replace(/\*/g, '')
      .trim();

    // Perform initial capture
    console.log('[GuidanceCoordinator] Performing initial capture...');
    this.lastFullCvTime = Date.now();
    this.captureAndMatchTarget().catch(console.error);

    // Get cached HWND for URL-based matching
    const cachedHwnd = this.state.matchedBrowserHwnd;

    // Start change detection - callback fires when screen changes
    this.screenChangeDetector.start(
      () => {
        // Screen changed (user scrolled) - use FAST position update instead of full CV
        // This finds the target label's new position using OCR-only (~5-10s vs ~50s)
        if (this.state.currentTarget?.label) {
          console.log('[GuidanceCoordinator] Screen change detected, running fast position update...');
          this.fastUpdateHaloPosition().catch(console.error);
        } else {
          // No current target - need full CV to find one
          const now = Date.now();
          const timeSinceLastCv = now - this.lastFullCvTime;

          if (timeSinceLastCv < this.FULL_CV_THROTTLE_MS) {
            console.log(`[GuidanceCoordinator] No target yet, throttling CV (${Math.round(timeSinceLastCv / 1000)}s since last run)`);
            return;
          }

          console.log('[GuidanceCoordinator] No target yet, running full CV analysis...');
          this.lastFullCvTime = now;
          this.captureAndMatchTarget().catch(console.error);
        }
      },
      targetPattern || undefined,
      cachedHwnd || undefined
    );

    console.log('[GuidanceCoordinator] Capture loop started (change detection mode)');
  }

  private stopCaptureLoop(): void {
    // Stop fixed interval capture
    if (this.captureIntervalId) {
      clearInterval(this.captureIntervalId);
      this.captureIntervalId = null;
    }

    // Stop fast verification monitor
    if (this.fastVerifyIntervalId) {
      clearInterval(this.fastVerifyIntervalId);
      this.fastVerifyIntervalId = null;
    }

    // Stop change detection
    if (this.screenChangeDetector) {
      this.screenChangeDetector.stop();
      this.screenChangeDetector = null;
    }

    console.log('Capture loop stopped');
  }

  private async captureAndMatchTarget(): Promise<void> {
    if (this.isDestroyed) {
      console.log('captureAndMatchTarget: Coordinator is destroyed, returning');
      return;
    }
    if (!this.state.session || !this.state.currentStep) {
      console.log('captureAndMatchTarget: No session or currentStep', {
        session: this.state.session?.session_id,
        currentStep: this.state.currentStep?.step_number,
      });
      return;
    }

    // Prevent concurrent captures - this is critical for performance
    // Multiple captures can stack up from interval + step changes
    if (this.isCaptureInProgress) {
      console.log('captureAndMatchTarget: Capture already in progress, skipping');
      return;
    }

    this.isCaptureInProgress = true;
    console.log('captureAndMatchTarget: Starting capture (locked)');

    try {
      // Get foreground window info for HWND tracking
      let foregroundWindow: ForegroundWindowInfo | null = null;
      try {
        foregroundWindow = await getForegroundWindowSimple();
        if (foregroundWindow) {
          console.log('Foreground window:', {
            hwnd: foregroundWindow.hwnd,
            title: foregroundWindow.title,
            process: foregroundWindow.process_name,
            isBrowser: foregroundWindow.is_browser,
          });
        }
      } catch (e) {
        console.warn('Failed to get foreground window info:', e);
      }

      // SMART WINDOW CAPTURE - No OCR verification needed!
      // We use reliable identification methods:
      // - Web apps: URL pattern matching (Windows UI Automation extracts URL from browser)
      // - Desktop apps: Process name matching
      // These methods directly identify the target, so no OCR verification is required.

      const targetPattern = this.state.targetAppSettings?.target_window_pattern;
      const urlPatterns = this.state.targetAppSettings?.target_url_patterns;
      const processName = this.state.targetAppSettings?.target_process_name;
      const brandKeywords = this.state.targetAppSettings?.target_brand_keywords;
      let imageBase64: string | undefined;
      let captureMethod: 'url' | 'process' | 'title' | 'keyword' | 'fullscreen' | null = null;

      // PRIORITY 1: URL pattern matching (most reliable for web apps)
      // Uses Python backend for reliable URL extraction from browser address bars
      if (urlPatterns && urlPatterns.length > 0) {
        console.log('[Capture] PRIMARY: Python-based URL pattern matching:', urlPatterns);
        try {
          // Use Python backend for browser URL detection (more reliable than Rust)
          const browserResult: BrowserUrlResponse = await detectBrowserWithUrl(urlPatterns);

          console.log('[Capture] Browser detection result:', browserResult);

          if (browserResult.found && browserResult.browser?.title) {
            console.log('[Capture] URL match found:', browserResult.browser.title);
            console.log('[Capture] Extracted URL:', browserResult.browser.url);
            console.log('[Capture] Matched pattern:', browserResult.matched_pattern);

            // Capture the browser window by title
            const captureResponse = await captureWindow(browserResult.browser.title);
            if (captureResponse.success && captureResponse.image_base64) {
              imageBase64 = captureResponse.image_base64;
              captureMethod = 'url';
              console.log('[Capture] URL-matched capture successful');

              // Cache the verified HWND for future fast position updates
              if (browserResult.browser.hwnd) {
                this.verifiedHwnds.add(browserResult.browser.hwnd);
                this.state.matchedBrowserHwnd = browserResult.browser.hwnd;
                console.log('[Capture] Cached browser HWND for fast updates:', browserResult.browser.hwnd);

                // Reset URL verification failure counter on successful Python detection
                this.urlVerificationFailureCount = 0;

                // Update ScreenChangeDetector with the new HWND
                if (this.screenChangeDetector) {
                  this.screenChangeDetector.setTargetHwnd(browserResult.browser.hwnd);
                }
              }
            }
          } else {
            console.log('[Capture] No browser with matching URL found');
            console.log('[Capture] Detection time:', browserResult.detection_time_ms, 'ms');
            console.log('[Capture] All browsers found:', browserResult.all_browsers);
          }
        } catch (e) {
          console.error('[Capture] URL match error:', e);
          // Fall back to Rust-based matching if Python backend fails
          try {
            console.log('[Capture] Falling back to Rust-based URL matching');
            const smartConfig: SmartMatchConfig = {
              mode: 'url',
              url_patterns: urlPatterns,
            };
            const smartResult = await smartMatchWindow(smartConfig);
            if (smartResult.matched && smartResult.window_info?.title) {
              const captureResponse = await captureWindow(smartResult.window_info.title);
              if (captureResponse.success && captureResponse.image_base64) {
                imageBase64 = captureResponse.image_base64;
                captureMethod = 'url';
                console.log('[Capture] Rust fallback URL-matched capture successful');
              }
            }
          } catch (fallbackError) {
            console.error('[Capture] Rust fallback also failed:', fallbackError);
          }
        }
      }

      // PRIORITY 2: Process name matching (reliable for desktop apps)
      if (!imageBase64 && processName) {
        console.log('[Capture] FALLBACK 1: Smart match with process name:', processName);
        try {
          const smartConfig: SmartMatchConfig = {
            mode: 'process',
            process_name: processName,
          };
          const smartResult = await smartMatchWindow(smartConfig);

          if (smartResult.matched && smartResult.window_info?.title) {
            console.log('[Capture] Process match found:', smartResult.window_info.title);

            const captureResponse = await captureWindow(smartResult.window_info.title);
            if (captureResponse.success && captureResponse.image_base64) {
              imageBase64 = captureResponse.image_base64;
              captureMethod = 'process';
              console.log('[Capture] Process-matched capture successful');
            }
          } else {
            console.log('[Capture] No window with matching process found');
          }
        } catch (e) {
          console.error('[Capture] Process match error:', e);
        }
      }

      // PRIORITY 3: Window title pattern (fallback)
      if (!imageBase64 && targetPattern) {
        const cleanPattern = targetPattern.replace(/\*/g, '').trim();
        console.log('[Capture] FALLBACK 2: Window title pattern:', cleanPattern);
        try {
          const captureResponse = await captureWindow(cleanPattern);
          if (captureResponse.success && captureResponse.image_base64) {
            imageBase64 = captureResponse.image_base64;
            captureMethod = 'title';
            console.log('[Capture] Title pattern capture successful');
          }
        } catch (e) {
          console.error('[Capture] Title pattern error:', e);
        }
      }

      // PRIORITY 4: Brand keywords in title (fallback)
      if (!imageBase64 && brandKeywords && brandKeywords.length > 0) {
        console.log('[Capture] FALLBACK 3: Brand keywords:', brandKeywords);
        try {
          for (const keyword of brandKeywords) {
            const captureResponse = await captureWindow(keyword);
            if (captureResponse.success && captureResponse.image_base64) {
              imageBase64 = captureResponse.image_base64;
              captureMethod = 'keyword';
              console.log('[Capture] Brand keyword capture successful:', keyword);
              break;
            }
          }
        } catch (e) {
          console.error('[Capture] Brand keyword error:', e);
        }
      }

      // PRIORITY 5: Full screen (last resort - skip CV analysis)
      if (!imageBase64) {
        console.warn('[Capture] LAST RESORT: Full screen capture');
        try {
          const captureResponse = await captureScreen();
          if (captureResponse.success && captureResponse.image_base64) {
            imageBase64 = captureResponse.image_base64;
            captureMethod = 'fullscreen';
          }
        } catch (e) {
          console.error('[Capture] Full screen capture failed:', e);
        }
      }

      if (!imageBase64) {
        console.error('[Capture] No image captured, cannot proceed');
        return;
      }

      // Full screen capture includes wrong windows - don't run CV analysis
      if (captureMethod === 'fullscreen') {
        console.warn('[Capture] Full screen fallback - skipping CV analysis (mixed content)');
        await hideHalo();
        this.state.currentTarget = null;
        return;
      }

      // Target window found via reliable method - update state
      console.log(`[Capture] Target identified via ${captureMethod} matching`);
      const wasActive = this.state.isTargetWindowActive;
      this.state.isTargetWindowActive = true;
      if (!wasActive) {
        this.emitEvent('target_window_found', { windowTitle: foregroundWindow?.title || '' });
      }

      // Step 2: Call backend to analyze and match target for current step
      // Note: imageBase64 was already captured via reliable method (URL/process matching)
      // Skip backend verification since frontend already verified target via smart matching
      const captureOptions: { hwnd?: number; skipVerification?: boolean } = {
        hwnd: foregroundWindow?.hwnd,
        skipVerification: true, // Already verified via URL/process matching
      };
      console.log('[CaptureStep] Calling backend for session:', this.state.session.session_id,
        'captureMethod:', captureMethod, 'hwnd:', captureOptions.hwnd);

      let captureResult;
      try {
        captureResult = await captureStep(this.state.session.session_id, imageBase64, captureOptions);
        console.log('captureStep result:', captureResult);
      } catch (apiError) {
        console.error('captureStep API error:', apiError);
        console.error('API error details:', {
          message: apiError instanceof Error ? apiError.message : String(apiError),
          response: (apiError as { response?: { status?: number; data?: unknown } })?.response?.status,
          responseData: (apiError as { response?: { status?: number; data?: unknown } })?.response?.data,
        });
        // Don't return early - let finally block release the lock
        // Just skip processing by setting captureResult to null
        captureResult = null;
      }

      if (!captureResult) {
        return; // Exit after finally releases the lock
      }

      // Handle visual verification response from backend (only if verification wasn't skipped)
      // When skipVerification is true, the backend assumes we already verified via URL/process matching
      if (!captureOptions.skipVerification && captureResult.target_verified !== undefined) {
        console.log('[Visual Verification] Backend result:', {
          verified: captureResult.target_verified,
          keywords: captureResult.verification_keywords_matched,
          hwndCached: captureResult.hwnd_cached,
        });

        if (!captureResult.target_verified) {
          // Not on target application - handle accordingly
          console.log('[Visual Verification] Not on target app:', captureResult.message);

          if (this.state.isTargetWindowActive) {
            this.state.isTargetWindowActive = false;
            this.emitEvent('target_window_lost', { windowTitle: foregroundWindow?.title || '' });
          }

          // Remove from verified cache if it was there
          if (foregroundWindow) {
            this.verifiedHwnds.delete(foregroundWindow.hwnd);
          }

          await hideHalo();
          this.state.currentTarget = null;
          return;
        }

        // Target verified - update cache and state
        if (captureResult.hwnd_cached && foregroundWindow) {
          this.verifiedHwnds.add(foregroundWindow.hwnd);
          console.log('[Visual Verification] HWND added to local cache:', foregroundWindow.hwnd);
        }

        // Update target window active state
        const wasActiveVer = this.state.isTargetWindowActive;
        this.state.isTargetWindowActive = true;
        if (!wasActiveVer) {
          console.log('[Visual Verification] Target window verified, emitting event');
          this.emitEvent('target_window_found', { windowTitle: foregroundWindow?.title || '' });
        }
      }

      console.log('Processing captureResult:', {
        success: captureResult.success,
        target_found: captureResult.target_found,
        hasTarget: !!captureResult.target,
        message: captureResult.message,
        stepNumber: captureResult.step_number,
        elementCount: captureResult.all_elements?.length || 0,
      });

      if (captureResult.success && captureResult.target_found && captureResult.target) {
        console.log('Target found, showing halo:', captureResult.target);
        await this.showTargetHalo(captureResult);
      } else {
        // No target found, hide halo
        console.log('No target found:', captureResult.message);
        await hideHalo();
        this.state.currentTarget = null;
      }
    } catch (error) {
      console.error('Capture and match failed:', error);
    } finally {
      // Always release the capture lock
      this.isCaptureInProgress = false;
      console.log('captureAndMatchTarget: Capture complete (unlocked)');
    }
  }
  // =============================================
  // Halo Display
  // =============================================

  private async showTargetHalo(captureResult: CaptureStepResponse): Promise<void> {
    if (!captureResult.target) return;

    const target = captureResult.target;

    // Convert backend bbox format to overlay format
    const bounds: BoundingBox = {
      x: target.bbox.x1,
      y: target.bbox.y1,
      width: target.bbox.x2 - target.bbox.x1,
      height: target.bbox.y2 - target.bbox.y1,
    };

    console.log('showTargetHalo - bounds:', bounds, 'target:', target);
    console.log('showTargetHalo - captureResult.timing:', captureResult.timing);

    this.state.currentTarget = target;
    // Store timing for side panel display
    this.state.lastTiming = captureResult.timing || null;
    console.log('showTargetHalo - stored lastTiming:', this.state.lastTiming);

    // Update side panel with timing info
    if (this.state.currentStep) {
      await this.updateSidePanel(this.state.currentStep);
    }

    // Show or update halo
    if (this.config.showHaloOnStepChange) {
      const label = target.label || captureResult.instruction;

      if (this.state.status === 'showing_halo') {
        console.log('Updating halo position');
        await updateGuidanceStepHalo(
          bounds,
          target.step_number,
          label,
          target.target_id,
          captureResult.instruction,
          target.action_type,
          target.element_type
        );
      } else {
        console.log('Showing new halo');
        const result = await showGuidanceStepHalo(
          bounds,
          target.step_number,
          label,
          target.target_id,
          captureResult.instruction,
          target.action_type,
          target.element_type
        );
        console.log('showGuidanceStepHalo result:', result);
        this.updateStatus('showing_halo');
      }

      this.emitEvent('step_target_found', {
        step: this.state.currentStep,
        target,
        bounds,
      });
    }
  }

  // =============================================
  // State Management
  // =============================================

  private updateStatus(status: CoordinatorStatus): void {
    const previousStatus = this.state.status;
    this.state.status = status;
    this.state.lastUpdateTime = Date.now();

    if (previousStatus !== status) {
      this.emitEvent('status_changed', {
        previousStatus,
        newStatus: status
      });

      // Update the side panel status
      this.updatePanelStatus().catch(console.error);
    }
  }

  private handleError(message: string, error: unknown): void {
    const errorMessage = error instanceof Error ? error.message : String(error);
    this.state.error = `${message}: ${errorMessage}`;
    this.updateStatus('error');
    this.emitEvent('error', { message, error: errorMessage });
    console.error('GuidanceCoordinator error:', message, error);
  }

  private emitEvent(type: CoordinatorEventType, data: unknown): void {
    const event: CoordinatorEvent = {
      type,
      data,
      timestamp: Date.now(),
    };

    const listeners = this.eventListeners.get(type);
    if (listeners) {
      listeners.forEach(callback => {
        try {
          callback(event);
        } catch (error) {
          console.error('Event listener error:', error);
        }
      });
    }
  }
}

// =============================================
// Singleton Instance
// =============================================

let coordinatorInstance: GuidanceCoordinator | null = null;

/**
 * Get the singleton coordinator instance
 */
export function getCoordinator(config?: Partial<CoordinatorConfig>): GuidanceCoordinator {
  if (!coordinatorInstance) {
    coordinatorInstance = new GuidanceCoordinator(config);
  }
  return coordinatorInstance;
}

/**
 * Reset the coordinator (for testing or re-initialization)
 */
export async function resetCoordinator(): Promise<void> {
  if (coordinatorInstance) {
    await coordinatorInstance.destroy();
    coordinatorInstance = null;
  }
}

export { GuidanceCoordinator };
export default GuidanceCoordinator;
