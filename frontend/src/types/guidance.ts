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
  app_id?: string; // Target application ID for smart window matching
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

// =============================================
// Step Capture Types (for per-step CV analysis)
// =============================================

export interface DetectedElement {
  element_id: string;
  element_type: string;
  label: string | null;
  bbox: BoundingBox;
  confidence: number;
  metadata: Record<string, unknown>;
}

/**
 * Per-region timing breakdown for OCR text recognition diagnostic.
 */
export interface RecognitionRegionTiming {
  region_index: number;
  crop_width: number;
  crop_height: number;
  preprocess_ms: number;
  inference_ms: number;
  decode_ms: number;
  total_ms: number;
  text: string;  // Recognized text (truncated for display)
  confidence: number;
}

/**
 * Per-phase timing breakdown for UI element detection (from Ultralytics/YOLO).
 */
export interface DetectionTiming {
  preprocess_ms: number;  // Image preprocessing (resize, normalize)
  inference_ms: number;   // Neural network forward pass
  postprocess_ms: number;  // NMS, box filtering, etc.
  total_ms: number;       // Sum of all phases
}

/**
 * Detailed timing breakdown for CV analysis.
 * Shows time spent in each processing stage.
 */
export interface TimingBreakdown {
  total_ms: number;
  preprocessing_ms: number;
  detection_ms: number;  // UI element detection (OmniParser/YOLO)
  detection_timing?: DetectionTiming | null;  // Per-phase detection breakdown
  ocr_ms: number;  // Total OCR time
  ocr_detection_ms: number;  // Text detection phase within OCR
  ocr_recognition_ms: number;  // Text recognition phase within OCR
  matching_ms: number;
  verification_ms: number;
  element_count: number;
  text_region_count: number;
  // Per-region timing breakdown (only populated in diagnostic mode)
  region_timings?: RecognitionRegionTiming[] | null;
}

export interface StartGuidanceResponse {
  success: boolean;
  session_id: string;
  status: string;
  current_step: number;
  total_steps: number;
  target_app_configured: boolean;
  target_window_found: boolean;
  target_window_title: string | null;
  current_target: HaloTarget | null;
  message: string;
}

export interface CaptureStepResponse {
  success: boolean;
  session_id: string;
  step_number: number;
  instruction: string;
  target_found: boolean;
  target: HaloTarget | null;
  all_elements: DetectedElement[];
  capture_time_ms: number;
  match_confidence: number;
  message: string;
  window_title: string | null;
  // Visual verification fields
  target_verified: boolean;  // Whether target app was verified via brand keywords
  verification_keywords_matched: string[];  // Which keywords were found
  hwnd_cached: boolean;  // Whether HWND was cached for future quick checks
  // Timing breakdown for performance analysis
  timing?: TimingBreakdown | null;
}

// =============================================
// Target Application Settings Types
// =============================================

/**
 * Smart match mode for target application detection.
 * - 'url': Match browser URL against patterns (best for websites)
 * - 'process': Match process name (best for desktop apps)
 * - 'title': Match window title (legacy fallback)
 * - 'auto': Auto-detect - try URL first (if browser), then process, then title
 */
export type SmartMatchMode = 'url' | 'process' | 'title' | 'auto';

export interface TargetAppSettings {
  org_id: string;
  target_app_name: string | null;
  target_window_pattern: string | null;
  target_process_name: string | null;
  target_window_class: string | null;
  target_app_config: Record<string, unknown> | null;
  // Smart matching fields
  target_match_mode: SmartMatchMode;
  target_url_pattern: string | null;
  target_url_patterns: string[] | null;
  target_brand_keywords: string[] | null;  // Keywords for visual verification via OCR
  is_configured: boolean;
}

export interface UpdateTargetAppRequest {
  target_app_name?: string;
  target_window_pattern?: string;
  target_process_name?: string;
  target_window_class?: string;
  target_app_config?: Record<string, unknown>;
  // Smart matching fields
  target_match_mode?: SmartMatchMode;
  target_url_pattern?: string;
  target_url_patterns?: string[];
}

export interface UpdateTargetAppResponse {
  success: boolean;
  message: string;
  target_app: TargetAppSettings;
}

export interface WindowInfo {
  window_handle: number;
  title: string;
  process_name: string;
  process_id: number;
  is_visible: boolean;
  is_minimized: boolean;
  rect: {
    left: number;
    top: number;
    right: number;
    bottom: number;
  };
}

export interface DetectWindowsResponse {
  windows: WindowInfo[];
  total: number;
  matching_window: WindowInfo | null;
}

export interface ValidatePatternResponse {
  pattern: string;
  is_valid: boolean;
  matching_windows: WindowInfo[];
  error_message: string | null;
}

// =============================================
// Multi-Target Application Types (New Model)
// =============================================

/**
 * Full target application record from the database.
 * Supports multiple target apps per organisation.
 */
export interface TargetApplication {
  app_id: string;
  org_id: string;
  app_name: string;
  description: string | null;

  // Matching configuration
  match_mode: SmartMatchMode;
  url_pattern: string | null;
  url_patterns: string[] | null;
  brand_keywords: string[] | null;  // Keywords for visual verification via OCR
  process_name: string | null;
  window_pattern: string | null;
  window_class: string | null;
  app_config: Record<string, unknown> | null;

  // Status
  is_active: boolean;
  is_default: boolean;
  is_configured: boolean;

  // Timestamps
  created_at: string;
  updated_at: string;
}

/**
 * Request to create a new target application.
 */
export interface TargetAppCreateRequest {
  app_name: string;
  description?: string;
  match_mode?: SmartMatchMode;
  url_pattern?: string;
  url_patterns?: string[];
  brand_keywords?: string[];  // Keywords for visual verification via OCR
  process_name?: string;
  window_pattern?: string;
  window_class?: string;
  app_config?: Record<string, unknown>;
  is_active?: boolean;
  is_default?: boolean;
}

/**
 * Request to update an existing target application.
 */
export interface TargetAppUpdateRequest {
  app_name?: string;
  description?: string;
  match_mode?: SmartMatchMode;
  url_pattern?: string;
  url_patterns?: string[];
  brand_keywords?: string[];  // Keywords for visual verification via OCR
  process_name?: string;
  window_pattern?: string;
  window_class?: string;
  app_config?: Record<string, unknown>;
  is_active?: boolean;
}

/**
 * Response for list of target applications.
 */
export interface TargetAppListResponse {
  target_apps: TargetApplication[];
  total_count: number;
}

/**
 * Response for delete operation.
 */
export interface TargetAppDeleteResponse {
  success: boolean;
  message: string;
  app_id: string;
}

/**
 * Response for set default operation.
 */
export interface SetDefaultResponse {
  success: boolean;
  message: string;
  app_id: string;
  previous_default_id: string | null;
}
