// Guidance types for RAG-based Q&A

export interface RAGQueryRequest {
  query: string;
  kb_id?: string;
  top_k?: number;
  min_similarity?: number;
  include_metadata?: boolean;
}

export interface ChunkResult {
  chunk_id: string;
  doc_id: string;
  doc_name: string;
  chunk_text: string;
  similarity: number;
  metadata: Record<string, unknown>;
}

export interface RAGQueryResponse {
  success: boolean;
  query_id: string;
  query: string;
  results: ChunkResult[];
  total_results: number;
  search_time_ms: number;
}

// Local chat message type (for frontend state only)
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: ChunkResult[];
  timestamp: Date;
  isLoading?: boolean;
}

// =============================================
// AI Guidance Engine Types (Phase 6)
// =============================================

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface HaloTarget {
  target_id: string;
  bbox: BoundingBox;
  element_type: string;
  label: string | null;
  step_number: number;
  action_type: string;
  confidence: number;
}

export interface GuidanceStep {
  step_id: string;
  step_number: number;
  instruction: string;
  detailed_instruction: string | null;
  action_type: string;
  action_value: string | null;
  target: HaloTarget | null;
  match_confidence: number;
  status: 'pending' | 'current' | 'completed' | 'skipped' | 'failed';
}

export interface GuidanceSession {
  session_id: string;
  query: string;
  status: 'active' | 'paused' | 'completed' | 'abandoned' | 'error';
  current_step: number;
  total_steps: number;
  application_context: string | null;
  overall_confidence: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface GuidanceSessionDetail extends GuidanceSession {
  context_summary: string | null;
  steps: GuidanceStep[];
  current_target: HaloTarget | null;
}

// Request types
export interface GenerateGuidanceRequest {
  query: string;
  kb_id?: string;
  application_context?: string;
  include_screen_capture?: boolean;
}

// Response types
export interface GenerateGuidanceResponse {
  success: boolean;
  session_id: string;
  query: string;
  total_steps: number;
  context_summary: string | null;
  overall_confidence: number;
  steps: GuidanceStep[];
  current_target: HaloTarget | null;
}

export interface AdvanceStepResponse {
  success: boolean;
  session_id: string;
  previous_step: number;
  current_step: number;
  is_completed: boolean;
  current_target: HaloTarget | null;
  message: string;
}

export interface SessionListResponse {
  sessions: GuidanceSession[];
  total: number;
}

export interface SessionStateResponse {
  session_id: string;
  status: string;
  current_step: number;
  total_steps: number;
  query: string;
  steps: GuidanceStep[];
  current_target: HaloTarget | null;
}

export interface GuidanceHealthResponse {
  status: string;
  llm: {
    status: string;
    provider: string;
    model: string;
    available: boolean;
    fallback_available: boolean;
  };
  rag_available: boolean;
  cv_available: boolean;
}
