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
  imageBase64?: string
): Promise<CaptureStepResponse> => {
  // Always send a body object - FastAPI Body() requires consistent format
  const payload = {
    image_base64: imageBase64 || null,
    force_capture: false,
  };
  const response = await apiClient.post<CaptureStepResponse>(
    `/guidance/sessions/${sessionId}/capture`,
    payload
  );
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
