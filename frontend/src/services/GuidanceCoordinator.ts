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
  type SmartMatchResult,
  type ForegroundWindowInfo,
} from '../api/detection';
import type { SmartMatchMode } from '../types/guidance';
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
import { getTargetAppSettings, getTargetApp, captureStep, fastVerifyTarget, fastPositionUpdate, type FastVerifyResponse, type FastPositionUpdateResponse } from '../api/guidance';
import type {
  GuidanceSession,
  GuidanceStep,
  HaloTarget,
  TargetAppSettings,
  CaptureStepResponse,
  TargetApplication,
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
  private lastForegroundHwnd: number | null = null; // Track foreground window for visual verification
  private verifiedHwnds: Set<number> = new Set(); // HWNDs verified by backend
  private fastVerifyIntervalId: ReturnType<typeof setInterval> | null = null; // Fast verification monitor
  private lastFullCvTime: number = 0; // Throttle full CV analysis
  private readonly FULL_CV_THROTTLE_MS = 30000; // Only run full CV every 30 seconds max

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

    console.log('[FastVerifyMonitor] Starting fast verification monitor (every 3s)');

    // Run every 3 seconds to quickly detect when user leaves target
    this.fastVerifyIntervalId = setInterval(async () => {
      await this.runFastVerificationCheck();
    }, 3000);
  }

  /**
   * Fast update halo position using OCR-only (for scroll handling).
   * Much faster than full CV analysis (~5-10s vs ~50s).
   */
  private async fastUpdateHaloPosition(): Promise<void> {
    if (!this.state.currentTarget?.label || !this.state.session) {
      return;
    }

    // Capture screen
    const targetPattern = this.state.targetAppSettings?.target_window_pattern;
    let imageBase64: string | undefined;

    try {
      if (targetPattern) {
        const cleanPattern = targetPattern.replace(/\*/g, '').trim();
        const captureResponse = await captureWindow(cleanPattern);
        if (captureResponse.success && captureResponse.image_base64) {
          imageBase64 = captureResponse.image_base64;
        }
      } else {
        const captureResponse = await captureScreen();
        if (captureResponse.success && captureResponse.image_base64) {
          imageBase64 = captureResponse.image_base64;
        }
      }
    } catch {
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
      });

      const endTime = performance.now();
      console.log(`[FastPositionUpdate] Completed in ${(endTime - startTime).toFixed(0)}ms, found: ${result.found}`);

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
   * If not, immediately hide halo without waiting for full CV.
   */
  private async runFastVerificationCheck(): Promise<void> {
    // Don't run if full CV is in progress (it will handle verification)
    if (this.isCaptureInProgress) {
      return;
    }

    const hasBrandKeywords = this.state.targetAppSettings?.target_brand_keywords &&
      this.state.targetAppSettings.target_brand_keywords.length > 0;

    if (!hasBrandKeywords) {
      return;
    }

    // Get foreground window
    let foregroundWindow: ForegroundWindowInfo | null = null;
    try {
      foregroundWindow = await getForegroundWindowSimple();
    } catch {
      return;
    }

    // If HWND is already verified, no need to check
    if (foregroundWindow && this.verifiedHwnds.has(foregroundWindow.hwnd)) {
      return;
    }

    // Capture screen for verification
    const targetPattern = this.state.targetAppSettings?.target_window_pattern;
    let verifyImageBase64: string | undefined;

    try {
      if (targetPattern) {
        const cleanPattern = targetPattern.replace(/\*/g, '').trim();
        const captureResponse = await captureWindow(cleanPattern);
        if (captureResponse.success && captureResponse.image_base64) {
          verifyImageBase64 = captureResponse.image_base64;
        }
      } else {
        const captureResponse = await captureScreen();
        if (captureResponse.success && captureResponse.image_base64) {
          verifyImageBase64 = captureResponse.image_base64;
        }
      }
    } catch {
      return;
    }

    if (!verifyImageBase64) {
      return;
    }

    // Run fast verification
    try {
      console.log('[FastVerifyMonitor] Running quick check...');
      const fastResult = await fastVerifyTarget({
        image_base64: verifyImageBase64,
        brand_keywords: this.state.targetAppSettings!.target_brand_keywords!,
        hwnd: foregroundWindow?.hwnd || null,
      });

      console.log('[FastVerifyMonitor] Result:', fastResult.is_verified ? 'ON target' : 'OFF target');

      if (!fastResult.is_verified) {
        // User left target app - immediately hide halo
        console.log('[FastVerifyMonitor] User left target app, hiding halo immediately');

        if (this.state.isTargetWindowActive) {
          this.state.isTargetWindowActive = false;
          this.emitEvent('target_window_lost', { windowTitle: foregroundWindow?.title || '' });
        }

        if (foregroundWindow) {
          this.verifiedHwnds.delete(foregroundWindow.hwnd);
        }

        await hideHalo();
        this.state.currentTarget = null;
      } else {
        // User is on target - cache HWND
        if (fastResult.hwnd_cached && foregroundWindow) {
          this.verifiedHwnds.add(foregroundWindow.hwnd);
        }

        if (!this.state.isTargetWindowActive) {
          this.state.isTargetWindowActive = true;
          this.emitEvent('target_window_found', { windowTitle: foregroundWindow?.title || '' });
        }
      }
    } catch (error) {
      console.error('[FastVerifyMonitor] Error:', error);
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
    this.screenChangeDetector = getScreenChangeDetector({
      pollIntervalMs: this.config.changeDetectionPollMs,
      debounceMs: this.config.changeDetectionDebounceMs,
      detectWidth: 160,
      detectHeight: 120,
      changeThreshold: 0.05,
    });

    // Get target window pattern for focused capture
    const targetPattern = this.state.targetAppSettings?.target_window_pattern
      ?.replace(/\*/g, '')
      .trim();

    // Perform initial capture
    console.log('[GuidanceCoordinator] Performing initial capture...');
    this.lastFullCvTime = Date.now();
    this.captureAndMatchTarget().catch(console.error);

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
      targetPattern || undefined
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
          this.lastForegroundHwnd = foregroundWindow.hwnd;
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

      // VISUAL VERIFICATION APPROACH:
      // If brand keywords are configured, we use FAST verification (OCR-only) first
      // before running the expensive full CV analysis (~85 seconds).
      // This significantly improves responsiveness.
      const hasBrandKeywords = this.state.targetAppSettings?.target_brand_keywords &&
        this.state.targetAppSettings.target_brand_keywords.length > 0;

      // Check if this HWND is already verified (cached)
      const isHwndVerified = foregroundWindow &&
        this.verifiedHwnds.has(foregroundWindow.hwnd);

      if (hasBrandKeywords) {
        console.log('[Visual Verification] Brand keywords configured:', this.state.targetAppSettings?.target_brand_keywords);
        console.log('[Visual Verification] HWND verified (cached):', isHwndVerified);

        // If HWND is already verified, skip fast verification and go straight to full CV
        if (!isHwndVerified) {
          // Need to capture screen first for fast verification
          const targetPattern = this.state.targetAppSettings?.target_window_pattern;
          let verifyImageBase64: string | undefined;

          if (targetPattern) {
            const cleanPattern = targetPattern.replace(/\*/g, '').trim();
            try {
              const captureResponse = await captureWindow(cleanPattern);
              if (captureResponse.success && captureResponse.image_base64) {
                verifyImageBase64 = captureResponse.image_base64;
              }
            } catch {
              // Fallback to screen capture
              const fallback = await captureScreen();
              if (fallback.success && fallback.image_base64) {
                verifyImageBase64 = fallback.image_base64;
              }
            }
          } else {
            const captureResponse = await captureScreen();
            if (captureResponse.success && captureResponse.image_base64) {
              verifyImageBase64 = captureResponse.image_base64;
            }
          }

          if (verifyImageBase64) {
            // Run FAST verification (OCR-only, ~5-10 seconds vs ~85 seconds)
            console.log('[Visual Verification] Running FAST verification (OCR-only)...');
            const fastStartTime = performance.now();

            try {
              const fastResult: FastVerifyResponse = await fastVerifyTarget({
                image_base64: verifyImageBase64,
                brand_keywords: this.state.targetAppSettings!.target_brand_keywords!,
                hwnd: foregroundWindow?.hwnd || null,
              });

              const fastEndTime = performance.now();
              console.log(`[Visual Verification] FAST verification completed in ${(fastEndTime - fastStartTime).toFixed(0)}ms`);
              console.log('[Visual Verification] Result:', {
                verified: fastResult.is_verified,
                keywords: fastResult.matched_keywords,
                ocrTime: fastResult.ocr_time_ms,
                totalTime: fastResult.total_time_ms,
              });

              if (!fastResult.is_verified) {
                // Not on target application - hide halo and return early
                console.log('[Visual Verification] NOT on target app:', fastResult.message);

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
                return; // Skip full CV analysis
              }

              // Target verified via fast OCR
              console.log('[Visual Verification] Target VERIFIED via fast OCR');

              // Cache the verified HWND locally
              if (fastResult.hwnd_cached && foregroundWindow) {
                this.verifiedHwnds.add(foregroundWindow.hwnd);
                console.log('[Visual Verification] HWND added to local cache:', foregroundWindow.hwnd);
              }

              // Update target window active state
              const wasActive = this.state.isTargetWindowActive;
              this.state.isTargetWindowActive = true;
              if (!wasActive) {
                this.emitEvent('target_window_found', { windowTitle: foregroundWindow?.title || '' });
              }

            } catch (fastError) {
              console.error('[Visual Verification] Fast verification failed:', fastError);
              // Continue to full CV analysis as fallback
            }
          }
        } else {
          console.log('[Visual Verification] HWND already verified, skipping fast verification');
        }

        // Proceed to full CV analysis (for element matching)
      } else {
        // Legacy mode - use smart matching
        const matchResult = await this.checkTargetWindowSmart();

        console.log('Smart match result:', {
          matched: matchResult.matched,
          mode: matchResult.match_mode_used,
          pattern: matchResult.matched_pattern,
          debug: matchResult.debug_info,
        });

        if (!matchResult.matched && this.state.isTargetWindowActive) {
          console.log('Target window lost, hiding halo');
          this.state.isTargetWindowActive = false;
          this.emitEvent('target_window_lost', { windowTitle: matchResult.debug_info.window_title });
          await hideHalo();
          return;
        }

        if (!matchResult.matched) {
          console.log('Not on target window, skipping capture');
          return; // Don't capture if not on target window
        }

        console.log('Target window is active, proceeding to capture...');

        // Emit event when target window is first found
        const wasActive = this.state.isTargetWindowActive;
        this.state.isTargetWindowActive = true;
        if (!wasActive) {
          console.log('First time target found, emitting event');
          this.emitEvent('target_window_found', { windowTitle: matchResult.debug_info.window_title });
        }
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
      // Pass HWND for visual verification caching
      // IMPORTANT: Skip verification if we already verified via fast OCR endpoint
      // This avoids redundant OCR processing in the full CV pipeline
      const skipVerification = hasBrandKeywords || isHwndVerified;
      const captureOptions: { hwnd?: number; skipVerification?: boolean } = {
        hwnd: foregroundWindow?.hwnd,
        skipVerification: skipVerification || undefined,
      };
      console.log('[CaptureStep] skipVerification:', skipVerification, '(hasBrandKeywords:', hasBrandKeywords, ', isHwndVerified:', isHwndVerified, ')');
      console.log('About to call captureStep for session:', this.state.session.session_id,
        'with image:', !!imageBase64, 'hwnd:', captureOptions.hwnd, 'skipVerification:', captureOptions.skipVerification);

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
      // When skipVerification is true, the backend assumes we already verified via fast OCR
      if (!skipVerification && captureResult.target_verified !== undefined) {
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

  /**
   * Check if target window is active using smart matching.
   * Uses URL matching for browsers, process matching for desktop apps,
   * and falls back to title matching.
   */
  private async checkTargetWindowSmart(): Promise<SmartMatchResult> {
    const settings = this.state.targetAppSettings;

    // If no target configured, always match
    if (!settings?.is_configured) {
      return {
        matched: true,
        match_mode_used: 'none',
        window_info: null,
        matched_pattern: null,
        debug_info: {
          window_title: '',
          process_name: null,
          is_browser: false,
          browser_type: null,
          detected_url: null,
          detected_domain: null,
        },
      };
    }

    // Build smart match config from target app settings
    const config: SmartMatchConfig = {
      // Use match mode from settings, default to 'auto'
      mode: (settings.target_match_mode as SmartMatchMode) || 'auto',
      // URL patterns for website matching
      url_patterns: settings.target_url_patterns ||
        (settings.target_url_pattern ? [settings.target_url_pattern] : undefined),
      // Process name for desktop app matching
      process_name: settings.target_process_name || undefined,
      // Window title pattern (legacy fallback)
      title_pattern: settings.target_window_pattern || undefined,
    };

    console.log('[GuidanceCoordinator] Smart match config:', config);

    try {
      return await smartMatchWindow(config);
    } catch (error) {
      console.error('[GuidanceCoordinator] Smart match failed:', error);
      // Return no match on error
      return {
        matched: false,
        match_mode_used: 'error',
        window_info: null,
        matched_pattern: null,
        debug_info: {
          window_title: '',
          process_name: null,
          is_browser: false,
          browser_type: null,
          detected_url: null,
          detected_domain: null,
        },
      };
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
