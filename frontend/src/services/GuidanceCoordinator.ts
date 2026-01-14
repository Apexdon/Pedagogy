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
  getActiveWindowTitle,
  startWindowMonitoring,
  stopWindowMonitoring,
  isWindowMonitoringActive,
  captureScreen,
  captureWindow,
} from '../api/detection';
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
import { getTargetAppSettings, captureStep } from '../api/guidance';
import type {
  GuidanceSession,
  GuidanceStep,
  HaloTarget,
  TargetAppSettings,
  CaptureStepResponse,
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
}

export interface CoordinatorConfig {
  captureIntervalMs: number;
  windowPollIntervalMs: number;
  autoStartOnTargetWindow: boolean;
  showHaloOnStepChange: boolean;
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

  // Callback for external step advancement (set by useGuidanceCoordinator)
  public onPanelNextClicked: (() => Promise<void>) | null = null;
  public onPanelPrevClicked: (() => Promise<void>) | null = null;
  public onPanelSkipClicked: (() => Promise<void>) | null = null;
  public onPanelEndSession: (() => Promise<void>) | null = null;

  constructor(config?: Partial<CoordinatorConfig>) {
    this.config = {
      captureIntervalMs: 2000, // Capture every 2 seconds
      windowPollIntervalMs: 500, // Check window every 500ms
      autoStartOnTargetWindow: true,
      showHaloOnStepChange: true,
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
   */
  async initialize(session: GuidanceSession, steps: GuidanceStep[]): Promise<void> {
    if (this.isDestroyed) {
      throw new Error('Coordinator has been destroyed');
    }

    this.updateStatus('initializing');

    try {
      // Store session info and all steps for later lookup
      this.state.session = session;
      this.allSteps = steps;
      this.state.currentStep = steps.find(s => s.step_number === session.current_step) || steps[0];

      // Load target app settings
      await this.loadTargetAppSettings();

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
      this.state.currentTarget?.confidence || null
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

  private async loadTargetAppSettings(): Promise<void> {
    try {
      const settings = await getTargetAppSettings();
      this.state.targetAppSettings = settings;
    } catch (error) {
      console.warn('Could not load target app settings:', error);
      this.state.targetAppSettings = null;
    }
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
    if (this.captureIntervalId) return;

    // Initial capture
    this.captureAndMatchTarget().catch(console.error);

    // Setup interval
    this.captureIntervalId = setInterval(() => {
      this.captureAndMatchTarget().catch(console.error);
    }, this.config.captureIntervalMs);

    console.log('Capture loop started');
  }

  private stopCaptureLoop(): void {
    if (this.captureIntervalId) {
      clearInterval(this.captureIntervalId);
      this.captureIntervalId = null;
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
      // Check if target window is still active
      const windowInfo = await getActiveWindowTitle();
      const isTargetActive = this.isTargetWindow(windowInfo.title);

      console.log('Capture check - Window:', windowInfo.title, 'Pattern:', this.state.targetAppSettings?.target_window_pattern, 'Match:', isTargetActive);

      if (!isTargetActive && this.state.isTargetWindowActive) {
        console.log('Target window lost, hiding halo');
        this.state.isTargetWindowActive = false;
        this.emitEvent('target_window_lost', { windowTitle: windowInfo.title });
        await hideHalo();
        return;
      }

      if (!isTargetActive) {
        console.log('Not on target window, skipping capture');
        return; // Don't capture if not on target window
      }

      console.log('Target window is active, proceeding to capture...');

      // Emit event when target window is first found
      const wasActive = this.state.isTargetWindowActive;
      this.state.isTargetWindowActive = true;
      if (!wasActive) {
        console.log('First time target found, emitting event');
        this.emitEvent('target_window_found', { windowTitle: windowInfo.title });
      }

      // Step 1: Capture target window via Tauri (window-specific, not full screen)
      // This captures ONLY the target application window, excluding taskbar, sidebars, etc.
      let imageBase64: string | undefined;
      const targetPattern = this.state.targetAppSettings?.target_window_pattern;

      if (targetPattern) {
        // Strip wildcards from pattern for window title matching
        const cleanPattern = targetPattern.replace(/\*/g, '').trim();
        console.log('Capturing target window via Tauri, pattern:', cleanPattern);

        try {
          const captureResponse = await captureWindow(cleanPattern);
          if (captureResponse.success && captureResponse.image_base64) {
            imageBase64 = captureResponse.image_base64;
            console.log('Tauri window capture successful, captured:', captureResponse.monitor_name, 'image size:', imageBase64.length);
          } else {
            console.warn('Tauri window capture failed:', captureResponse.error);
            // Fallback to full screen capture
            console.log('Falling back to full screen capture...');
            const fallbackCapture = await captureScreen();
            if (fallbackCapture.success && fallbackCapture.image_base64) {
              imageBase64 = fallbackCapture.image_base64;
              console.log('Fallback screen capture successful');
            }
          }
        } catch (captureError) {
          console.error('Tauri window capture error:', captureError);
          // Fallback to full screen capture
          try {
            const fallbackCapture = await captureScreen();
            if (fallbackCapture.success && fallbackCapture.image_base64) {
              imageBase64 = fallbackCapture.image_base64;
              console.log('Fallback screen capture successful after error');
            }
          } catch (fallbackError) {
            console.error('Fallback capture also failed:', fallbackError);
          }
        }
      } else {
        // No target pattern, use full screen capture
        console.log('No target pattern, using full screen capture...');
        try {
          const captureResponse = await captureScreen();
          if (captureResponse.success && captureResponse.image_base64) {
            imageBase64 = captureResponse.image_base64;
            console.log('Tauri screen capture successful, image size:', imageBase64.length);
          } else {
            console.warn('Tauri capture failed:', captureResponse.error);
          }
        } catch (captureError) {
          console.error('Tauri capture error:', captureError);
        }
      }

      // Step 2: Call backend to analyze and match target for current step
      console.log('About to call captureStep for session:', this.state.session.session_id, 'with image:', !!imageBase64);
      let captureResult;
      try {
        captureResult = await captureStep(this.state.session.session_id, imageBase64);
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

  private isTargetWindow(windowTitle: string): boolean {
    if (!this.state.targetAppSettings?.target_window_pattern) {
      return true; // If no pattern, assume any window is valid
    }

    // Strip wildcard characters (*) from pattern for simple contains matching
    const pattern = this.state.targetAppSettings.target_window_pattern
      .replace(/\*/g, '')
      .toLowerCase()
      .trim();

    if (!pattern) {
      return true; // Empty pattern after stripping wildcards
    }

    return windowTitle.toLowerCase().includes(pattern);
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

    this.state.currentTarget = target;

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
