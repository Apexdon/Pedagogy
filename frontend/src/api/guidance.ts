import apiClient from './client';
import type {
  RAGQueryRequest,
  RAGQueryResponse,
  GenerateGuidanceRequest,
  GenerateGuidanceResponse,
  GuidanceSessionDetail,
  SessionListResponse,
  SessionStateResponse,
  AdvanceStepResponse,
  GuidanceHealthResponse,
  StartGuidanceResponse,
  CaptureStepResponse,
  TargetAppSettings,
  UpdateTargetAppRequest,
  UpdateTargetAppResponse,
  DetectWindowsResponse,
  ValidatePatternResponse,
  // Multi-target app types
  TargetApplication,
  TargetAppCreateRequest,
  TargetAppUpdateRequest,
  TargetAppListResponse,
  TargetAppDeleteResponse,
  SetDefaultResponse,
} from '@/types';

/**
 * Query the RAG system for guidance
 * Uses the existing /org/query/rag endpoint
 */
export const queryRAG = async (request: RAGQueryRequest): Promise<RAGQueryResponse> => {
  const response = await apiClient.post<RAGQueryResponse>('/org/query/rag', request);
  return response.data;
};

// =============================================
// AI Guidance Engine API (Phase 6)
// =============================================

/**
 * Generate step-by-step guidance for a user query
 */
export const generateGuidance = async (
  request: GenerateGuidanceRequest
): Promise<GenerateGuidanceResponse> => {
  const response = await apiClient.post<GenerateGuidanceResponse>('/guidance/generate', request);
  return response.data;
};

/**
 * List guidance sessions for the current user
 */
export const listGuidanceSessions = async (
  statusFilter?: string,
  limit?: number
): Promise<SessionListResponse> => {
  const params = new URLSearchParams();
  if (statusFilter) params.append('status_filter', statusFilter);
  if (limit) params.append('limit', limit.toString());

  const response = await apiClient.get<SessionListResponse>(
    `/guidance/sessions?${params.toString()}`
  );
  return response.data;
};

/**
 * Get detailed guidance session information
 */
export const getGuidanceSession = async (sessionId: string): Promise<GuidanceSessionDetail> => {
  const response = await apiClient.get<GuidanceSessionDetail>(`/guidance/sessions/${sessionId}`);
  return response.data;
};

/**
 * Get current session state (optimized for frequent polling)
 */
export const getSessionState = async (sessionId: string): Promise<SessionStateResponse> => {
  const response = await apiClient.get<SessionStateResponse>(
    `/guidance/sessions/${sessionId}/state`
  );
  return response.data;
};

/**
 * Advance to the next step
 */
export const advanceStep = async (sessionId: string): Promise<AdvanceStepResponse> => {
  const response = await apiClient.post<AdvanceStepResponse>(
    `/guidance/sessions/${sessionId}/advance`
  );
  return response.data;
};

/**
 * Skip the current step
 */
export const skipStep = async (sessionId: string): Promise<AdvanceStepResponse> => {
  const response = await apiClient.post<AdvanceStepResponse>(
    `/guidance/sessions/${sessionId}/skip`
  );
  return response.data;
};

/**
 * Jump to a specific step
 */
export const goToStep = async (
  sessionId: string,
  stepNumber: number
): Promise<SessionStateResponse> => {
  const response = await apiClient.post<SessionStateResponse>(
    `/guidance/sessions/${sessionId}/goto/${stepNumber}`
  );
  return response.data;
};

/**
 * Pause a guidance session
 */
export const pauseSession = async (sessionId: string): Promise<{ success: boolean }> => {
  const response = await apiClient.post<{ success: boolean }>(
    `/guidance/sessions/${sessionId}/pause`
  );
  return response.data;
};

/**
 * Resume a paused session
 */
export const resumeSession = async (sessionId: string): Promise<SessionStateResponse> => {
  const response = await apiClient.post<SessionStateResponse>(
    `/guidance/sessions/${sessionId}/resume`
  );
  return response.data;
};

/**
 * Abandon a guidance session
 */
export const abandonSession = async (sessionId: string): Promise<{ success: boolean }> => {
  const response = await apiClient.post<{ success: boolean }>(
    `/guidance/sessions/${sessionId}/abandon`
  );
  return response.data;
};

/**
 * Delete a guidance session and all related data
 */
export const deleteSession = async (sessionId: string): Promise<{ success: boolean }> => {
  const response = await apiClient.delete<{ success: boolean }>(
    `/guidance/sessions/${sessionId}`
  );
  return response.data;
};

/**
 * Check guidance engine health
 */
export const checkGuidanceHealth = async (): Promise<GuidanceHealthResponse> => {
  const response = await apiClient.get<GuidanceHealthResponse>('/guidance/health');
  return response.data;
};

// =============================================
// Active Guidance with Screen Capture (Per-Step CV)
// =============================================

/**
 * Start active guidance session with screen capture
 * This triggers the first screen capture and element detection
 */
export const startGuidance = async (sessionId: string): Promise<StartGuidanceResponse> => {
  const response = await apiClient.post<StartGuidanceResponse>(
    `/guidance/sessions/${sessionId}/start`
  );
  return response.data;
};

/**
 * Capture and analyze screen for current step
 * Captures target window, runs CV pipeline, and matches UI elements
 *
 * @param sessionId - The guidance session ID
 * @param imageBase64 - Optional base64 encoded screenshot from frontend (Tauri capture)
 */
export const captureStep = async (
  sessionId: string,
  imageBase64?: string,
  options?: {
    hwnd?: number;  // Window handle for visual verification caching
    skipVerification?: boolean;  // Skip visual verification if already verified
  }
): Promise<CaptureStepResponse> => {
  // Always send a body object - FastAPI Body() requires consistent format
  const payload = {
    image_base64: imageBase64 || null,
    force_capture: false,
    hwnd: options?.hwnd || null,
    skip_verification: options?.skipVerification || false,
  };
  const response = await apiClient.post<CaptureStepResponse>(
    `/guidance/sessions/${sessionId}/capture`,
    payload
  );
  console.log('[captureStep] API response timing:', response.data.timing);
  return response.data;
};

// =============================================
// Target Application Settings
// =============================================

/**
 * Get current target application settings for the org
 */
export const getTargetAppSettings = async (): Promise<TargetAppSettings> => {
  const response = await apiClient.get<TargetAppSettings>('/org/target-app');
  return response.data;
};

/**
 * Update target application settings for the org
 */
export const updateTargetAppSettings = async (
  settings: UpdateTargetAppRequest
): Promise<UpdateTargetAppResponse> => {
  const response = await apiClient.put<UpdateTargetAppResponse>('/org/target-app', settings);
  return response.data;
};

/**
 * Clear target application settings for the org
 */
export const clearTargetAppSettings = async (): Promise<{ success: boolean; message: string }> => {
  const response = await apiClient.delete<{ success: boolean; message: string }>('/org/target-app');
  return response.data;
};

/**
 * Detect all visible windows on the system
 */
export const detectWindows = async (): Promise<DetectWindowsResponse> => {
  const response = await apiClient.get<DetectWindowsResponse>('/org/windows');
  return response.data;
};

/**
 * Validate a window pattern by checking for matching windows
 */
export const validateWindowPattern = async (pattern: string): Promise<ValidatePatternResponse> => {
  const response = await apiClient.post<ValidatePatternResponse>('/org/validate-pattern', {
    pattern,
  });
  return response.data;
};

// =============================================
// Multi-Target Application API (New)
// =============================================

/**
 * List all target applications for the current organisation
 */
export const listTargetApps = async (activeOnly = false): Promise<TargetAppListResponse> => {
  const params = activeOnly ? '?active_only=true' : '';
  const response = await apiClient.get<TargetAppListResponse>(`/target-apps${params}`);
  return response.data;
};

/**
 * Get a specific target application by ID
 */
export const getTargetApp = async (appId: string): Promise<TargetApplication> => {
  const response = await apiClient.get<TargetApplication>(`/target-apps/${appId}`);
  return response.data;
};

/**
 * Get the default target application for the organisation
 */
export const getDefaultTargetApp = async (): Promise<TargetApplication | null> => {
  const response = await apiClient.get<TargetApplication | null>('/target-apps/default');
  return response.data;
};

/**
 * Create a new target application
 */
export const createTargetApp = async (data: TargetAppCreateRequest): Promise<TargetApplication> => {
  const response = await apiClient.post<TargetApplication>('/target-apps', data);
  return response.data;
};

/**
 * Update an existing target application
 */
export const updateTargetApp = async (
  appId: string,
  data: TargetAppUpdateRequest
): Promise<TargetApplication> => {
  const response = await apiClient.put<TargetApplication>(`/target-apps/${appId}`, data);
  return response.data;
};

/**
 * Delete a target application
 */
export const deleteTargetApp = async (appId: string): Promise<TargetAppDeleteResponse> => {
  const response = await apiClient.delete<TargetAppDeleteResponse>(`/target-apps/${appId}`);
  return response.data;
};

/**
 * Set a target application as the default
 */
export const setDefaultTargetApp = async (appId: string): Promise<SetDefaultResponse> => {
  const response = await apiClient.put<SetDefaultResponse>(`/target-apps/${appId}/default`);
  return response.data;
};

/**
 * Toggle a target application's active status
 */
export const toggleTargetAppActive = async (appId: string): Promise<TargetApplication> => {
  const response = await apiClient.put<TargetApplication>(`/target-apps/${appId}/toggle-active`);
  return response.data;
};

// =============================================
// Fast Visual Verification API
// =============================================

export interface FastVerifyRequest {
  image_base64: string;
  brand_keywords: string[];
  hwnd?: number | null;
}

export interface FastVerifyResponse {
  success: boolean;
  is_verified: boolean;
  matched_keywords: string[];
  confidence: number;
  verification_time_ms: number;
  ocr_time_ms: number;
  total_time_ms: number;
  hwnd_cached: boolean;
  page_hash_cached: boolean;  // True if verified from perceptual hash cache
  verification_method: 'page_hash' | 'hwnd' | 'ocr' | 'none' | 'error';
  message: string;
}

/**
 * Fast visual verification using OCR-only (no UI element detection).
 *
 * This endpoint is designed for quick target application verification:
 * - Runs ONLY OCR on the screenshot (skips slow OmniParser detection)
 * - Checks if brand keywords exist in the OCR text
 * - Returns within ~5-10 seconds (vs ~85 seconds for full CV analysis)
 *
 * Use this for:
 * - Quick verification before starting full CV analysis
 * - Continuous monitoring to detect when user navigates away
 * - Initial window matching before expensive element detection
 */
export const fastVerifyTarget = async (request: FastVerifyRequest): Promise<FastVerifyResponse> => {
  const response = await apiClient.post<FastVerifyResponse>('/guidance/verify-target', request);
  return response.data;
};

// =============================================
// Fast Position Update API (for scroll handling)
// =============================================

export interface FastPositionUpdateRequest {
  image_base64: string;
  target_label: string;
  current_bbox?: {
    x1: number;
    y1: number;
    x2: number;
    y2: number;
  } | null;
  session_id?: string;  // Session ID for reference image tracking
}

export interface FastPositionUpdateResponse {
  success: boolean;
  found: boolean;
  new_bbox?: {
    x1: number;
    y1: number;
    x2: number;
    y2: number;
  } | null;
  confidence: number;
  scroll_offset_y: number;  // Scroll offset detected (positive = scrolled down)
  detection_method: 'scroll_offset' | 'ocr_fallback' | 'none';  // How position was determined
  processing_time_ms: number;
  total_time_ms: number;
  message: string;
  reference_stored: boolean;  // Whether a new reference image was stored
}

/**
 * Fast halo position update using scroll offset detection.
 *
 * This endpoint is optimized for quick position updates when user scrolls:
 * - Compares current screenshot with stored reference image
 * - Detects scroll offset using template matching (~10-50ms)
 * - Applies offset to known bounding box
 *
 * Much faster than OCR-based detection (~10-50ms vs ~500-2000ms).
 */
export const fastPositionUpdate = async (request: FastPositionUpdateRequest): Promise<FastPositionUpdateResponse> => {
  const response = await apiClient.post<FastPositionUpdateResponse>('/guidance/update-position', request);
  return response.data;
};

// =============================================
// Browser URL Detection API (Python-based)
// =============================================

export interface BrowserInfo {
  hwnd: number;
  title: string;
  process_name: string;
  url: string | null;
  domain: string | null;
}

export interface BrowserUrlRequest {
  url_patterns: string[];
}

export interface BrowserUrlResponse {
  success: boolean;
  found: boolean;
  browser: BrowserInfo | null;
  matched_pattern: string | null;
  all_browsers: BrowserInfo[];
  message: string;
  detection_time_ms: number;
}

/**
 * Detect browser window with matching URL patterns using Python backend.
 *
 * This uses pywinauto to extract URLs from browser address bars via
 * Windows UI Automation. More reliable than the Rust-based implementation.
 *
 * @param urlPatterns - List of URL patterns to match (e.g., ["rs-online.com"])
 * @returns Browser info if found, including extracted URL
 */
export const detectBrowserWithUrl = async (urlPatterns: string[]): Promise<BrowserUrlResponse> => {
  const response = await apiClient.post<BrowserUrlResponse>('/guidance/detect-browser', {
    url_patterns: urlPatterns,
  });
  return response.data;
};
