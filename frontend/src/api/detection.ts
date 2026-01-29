/**
 * Detection API - Frontend interface for screen capture and analysis.
 *
 * Combines Tauri invoke commands with backend HTTP API calls.
 */

import { invoke as tauriInvoke } from '@tauri-apps/api/core';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';

// Check if running inside Tauri
const isTauri = (): boolean => {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
};

// Safe invoke that throws helpful error when not in Tauri
const invoke = async <T>(cmd: string, args?: Record<string, unknown>): Promise<T> => {
  if (!isTauri()) {
    throw new Error(
      `Tauri not available. Detection features require running the desktop app.\n` +
      `Run: cd frontend && npm run tauri dev`
    );
  }
  return tauriInvoke<T>(cmd, args);
};
import apiClient from './client';
import type {
  CaptureResponse,
  WindowInfo,
  WindowMatchEvent,
  StartMonitoringRequest,
  ScreenState,
  AnalyzeScreenRequest,
  DetectUIResponse,
  ExtractTextResponse,
  CVHealthResponse,
  MonitorInfo,
} from '@/types/detection';

// =============================================
// Tauri Commands (Rust backend)
// =============================================

/**
 * Captures the primary screen at full resolution.
 * Returns Base64 encoded PNG suitable for CV analysis.
 */
export async function captureScreen(): Promise<CaptureResponse> {
  return invoke<CaptureResponse>('capture_screenshot');
}

/**
 * Captures the screen at reduced resolution for faster processing.
 */
export async function captureScreenLowRes(
  maxWidth?: number,
  maxHeight?: number
): Promise<CaptureResponse> {
  return invoke<CaptureResponse>('capture_screenshot_low_res', {
    maxWidth,
    maxHeight,
  });
}

/**
 * Captures a specific region of the screen.
 */
export async function captureScreenRegion(
  x: number,
  y: number,
  width: number,
  height: number
): Promise<CaptureResponse> {
  return invoke<CaptureResponse>('capture_screenshot_region', {
    x,
    y,
    width,
    height,
  });
}

/**
 * Captures a specific window by title pattern.
 * This captures ONLY the target window, not the entire screen.
 */
export async function captureWindow(titlePattern: string): Promise<CaptureResponse> {
  return invoke<CaptureResponse>('capture_window', {
    titlePattern,
  });
}

/**
 * Captures a specific window by its HWND (window handle).
 * This is more efficient than title matching when the HWND is already known,
 * such as after a successful URL-based browser detection.
 */
export async function captureWindowByHwnd(hwnd: number): Promise<CaptureResponse> {
  return invoke<CaptureResponse>('capture_window_by_hwnd', {
    hwnd,
  });
}

/**
 * Gets the title of the currently active window.
 */
export async function getActiveWindowTitle(): Promise<WindowInfo> {
  return invoke<WindowInfo>('get_active_window_title');
}

/**
 * Gets information about all available monitors.
 */
export async function getMonitors(): Promise<MonitorInfo[]> {
  return invoke<MonitorInfo[]>('get_monitors');
}

/**
 * Starts monitoring for windows matching specified patterns.
 */
export async function startWindowMonitoring(
  request: StartMonitoringRequest
): Promise<void> {
  return invoke('start_window_monitoring', { request });
}

/**
 * Stops window monitoring.
 */
export async function stopWindowMonitoring(): Promise<void> {
  return invoke('stop_window_monitoring');
}

/**
 * Checks if window monitoring is currently active.
 */
export async function isWindowMonitoringActive(): Promise<boolean> {
  return invoke<boolean>('is_window_monitoring_active');
}

// =============================================
// Smart Window Matching (Phase 8)
// =============================================

/**
 * Smart match mode for target application detection.
 */
export type SmartMatchMode = 'url' | 'process' | 'title' | 'auto';

/**
 * Configuration for smart window matching.
 */
export interface SmartMatchConfig {
  mode: SmartMatchMode;
  url_patterns?: string[];
  process_name?: string;
  title_pattern?: string;
}

/**
 * Extended window information including URL for browsers.
 */
export interface ExtendedWindowInfo {
  title: string;
  process_name: string;
  process_id: number;
  hwnd: number;
  is_browser: boolean;
  browser_type: string | null;
  url: string | null;
  url_domain: string | null;
  /** Full origin (scheme + domain + port) - stays same across page navigations */
  url_origin: string | null;
}

/**
 * Debug info for smart matching.
 */
export interface SmartMatchDebugInfo {
  window_title: string;
  process_name: string | null;
  is_browser: boolean;
  browser_type: string | null;
  detected_url: string | null;
  detected_domain: string | null;
}

/**
 * Result of smart window matching.
 */
export interface SmartMatchResult {
  matched: boolean;
  match_mode_used: string;
  window_info: ExtendedWindowInfo | null;
  matched_pattern: string | null;
  debug_info: SmartMatchDebugInfo;
  /** Window handle for caching (available when matched) */
  hwnd: number | null;
}

/**
 * Gets extended window information including URL for browsers.
 * Uses Windows UI Automation to extract browser URL from address bar.
 */
export async function getExtendedWindowInfo(): Promise<ExtendedWindowInfo | null> {
  return invoke<ExtendedWindowInfo | null>('get_extended_window_info');
}

/**
 * Performs smart window matching using multiple strategies.
 *
 * This is the main function for smart target application detection:
 * - URL: Match browser URL against patterns (best for websites)
 * - Process: Match process name (best for desktop apps)
 * - Title: Match window title (legacy fallback)
 * - Auto: Try all strategies in order (URL -> Process -> Title)
 */
export async function smartMatchWindow(config: SmartMatchConfig): Promise<SmartMatchResult> {
  return invoke<SmartMatchResult>('smart_match_window', { config });
}

/**
 * Debug info for a browser window
 */
export interface BrowserWindowDebugInfo {
  title: string;
  process_name: string;
}

/**
 * Lists all open browser windows for debugging.
 * Useful for discovering what window titles are available for matching.
 */
export async function listBrowserWindows(): Promise<BrowserWindowDebugInfo[]> {
  return invoke<BrowserWindowDebugInfo[]>('list_browser_windows');
}

/**
 * Simple foreground window info for visual verification approach.
 * The backend will verify if this is the target app using OCR on the screenshot.
 */
export interface ForegroundWindowInfo {
  /** Window handle as number for caching/comparison */
  hwnd: number;
  /** Window title */
  title: string;
  /** Process name (e.g., "chrome.exe", "msedge.exe") */
  process_name: string;
  /** Whether this appears to be a browser window */
  is_browser: boolean;
}

/**
 * Gets simple foreground window info for visual verification.
 * This is a lightweight command that just returns the foreground window's
 * HWND, title, and process name. The backend will verify if this is the
 * target application using OCR-based brand keyword matching on the screenshot.
 */
export async function getForegroundWindowSimple(): Promise<ForegroundWindowInfo | null> {
  return invoke<ForegroundWindowInfo | null>('get_foreground_window_simple');
}

// =============================================
// Event Listeners
// =============================================

/**
 * Listen for window match events during monitoring.
 */
export async function onWindowMatch(
  callback: (event: WindowMatchEvent) => void
): Promise<UnlistenFn> {
  return listen<WindowMatchEvent>('window-match', (event) => {
    callback(event.payload);
  });
}

// =============================================
// Backend API (Python CV Pipeline)
// =============================================

/**
 * Analyzes a screenshot using the CV pipeline.
 * Performs UI detection and OCR.
 */
export async function analyzeScreen(
  request: AnalyzeScreenRequest
): Promise<ScreenState> {
  const response = await apiClient.post<ScreenState>(
    '/capture/analyze',
    request
  );
  return response.data;
}

/**
 * Detects UI elements only (no OCR).
 */
export async function detectUIElements(
  imageBase64: string,
  resize = true
): Promise<DetectUIResponse> {
  const response = await apiClient.post<DetectUIResponse>('/capture/detect-ui', {
    image: imageBase64,
    resize,
  });
  return response.data;
}

/**
 * Extracts text only (no UI detection).
 */
export async function extractText(
  imageBase64: string,
  resize = true
): Promise<ExtractTextResponse> {
  const response = await apiClient.post<ExtractTextResponse>('/capture/extract-text', {
    image: imageBase64,
    resize,
  });
  return response.data;
}

/**
 * Gets CV pipeline health status.
 */
export async function getCVHealth(): Promise<CVHealthResponse> {
  const response = await apiClient.get<CVHealthResponse>('/capture/health');
  return response.data;
}

// =============================================
// Combined Operations
// =============================================

/**
 * Captures and analyzes the screen in one operation.
 *
 * This is the main function for the detection workflow:
 * 1. Captures screen via Tauri command
 * 2. Sends to backend for CV analysis
 * 3. Returns complete screen state
 */
export async function captureAndAnalyze(options?: {
  resize?: boolean;
  fuseLabels?: boolean;
}): Promise<{
  capture: CaptureResponse;
  analysis: ScreenState;
}> {
  const { resize = true, fuseLabels = true } = options || {};

  // Step 1: Capture screen
  const captureResult = await captureScreen();

  if (!captureResult.success || !captureResult.image_base64) {
    throw new Error(captureResult.error || 'Screen capture failed');
  }

  // Step 2: Analyze with CV pipeline
  const analysis = await analyzeScreen({
    image: captureResult.image_base64,
    resize,
    fuse_labels: fuseLabels,
  });

  return {
    capture: captureResult,
    analysis,
  };
}

/**
 * Captures screen and detects UI elements only (faster than full analysis).
 */
export async function captureAndDetectUI(resize = true): Promise<{
  capture: CaptureResponse;
  detection: DetectUIResponse;
}> {
  const captureResult = await captureScreen();

  if (!captureResult.success || !captureResult.image_base64) {
    throw new Error(captureResult.error || 'Screen capture failed');
  }

  const detection = await detectUIElements(captureResult.image_base64, resize);

  return {
    capture: captureResult,
    detection,
  };
}

/**
 * Captures screen and extracts text only (faster than full analysis).
 */
export async function captureAndExtractText(resize = true): Promise<{
  capture: CaptureResponse;
  textExtraction: ExtractTextResponse;
}> {
  const captureResult = await captureScreen();

  if (!captureResult.success || !captureResult.image_base64) {
    throw new Error(captureResult.error || 'Screen capture failed');
  }

  const textExtraction = await extractText(captureResult.image_base64, resize);

  return {
    capture: captureResult,
    textExtraction,
  };
}
