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
