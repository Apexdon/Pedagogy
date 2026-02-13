// Detection and Screen Capture Types

// =============================================
// Screen Capture Types (from Rust)
// =============================================

export interface CaptureResult {
  image_base64: string;
  width: number;
  height: number;
  monitor_name: string;
}

export interface CaptureResponse {
  success: boolean;
  image_base64?: string;
  width?: number;
  height?: number;
  monitor_name?: string;
  error?: string;
}

export interface MonitorInfo {
  name: string;
  is_primary: boolean;
  width: number;
  height: number;
  x: number;
  y: number;
}

// =============================================
// Window Monitoring Types
// =============================================

export interface WindowInfo {
  title: string;
  process_name?: string;
}

export type MatchMode = 'contains' | 'startsWith' | 'endsWith' | 'exact' | 'regex';

export interface WindowPattern {
  pattern: string;
  mode?: MatchMode;
  case_sensitive?: boolean;
}

export interface WindowMatchEvent {
  window_info: WindowInfo;
  matched_pattern: string;
  timestamp: number;
}

export interface StartMonitoringRequest {
  patterns: WindowPattern[];
  poll_interval_ms?: number;
}

// =============================================
// Screen State Types (from CV Pipeline Backend)
// =============================================

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface UIElement {
  element_id: string;
  type: string;
  label: string | null;
  bbox: BoundingBox;
  confidence: number;
  metadata: Record<string, unknown>;
}

export interface TextRegion {
  text: string;
  bbox: BoundingBox;
  confidence: number;
  metadata: Record<string, unknown>;
}

export interface ImageSize {
  width: number;
  height: number;
}

export interface ScreenState {
  capture_id: string;
  timestamp: string;
  image_size: ImageSize;
  elements: UIElement[];
  text_regions: TextRegion[];
  processing_time_ms: number;
  metadata: Record<string, unknown>;
}

// =============================================
// Detection State Machine Types
// =============================================

export type DetectionStatus =
  | 'idle'
  | 'capturing'
  | 'analyzing'
  | 'ready'
  | 'error';

export interface DetectionSession {
  session_id: string;
  started_at: Date;
  status: DetectionStatus;
  capture?: CaptureResult;
  screen_state?: ScreenState;
  error?: string;
}

// =============================================
// API Request/Response Types
// =============================================

export interface AnalyzeScreenRequest {
  image: string; // Base64 encoded image
  resize?: boolean;
  fuse_labels?: boolean;
}

export interface AnalyzeScreenResponse extends ScreenState {
  // Inherits all ScreenState fields
}

export interface DetectUIRequest {
  image: string;
  resize?: boolean;
}

export interface DetectUIResponse {
  elements: UIElement[];
  element_count: number;
  image_size: ImageSize;
  processing_time_ms: number;
}

export interface ExtractTextRequest {
  image: string;
  resize?: boolean;
}

export interface ExtractTextResponse {
  text_regions: TextRegion[];
  full_text: string;
  image_size: ImageSize;
  processing_time_ms: number;
}

export interface CVHealthResponse {
  status: string;
  detector: {
    loaded: boolean;
    model: string;
  };
  ocr_engine: {
    loaded: boolean;
    languages: string[];
  };
  preprocessor: {
    max_width: number;
    max_height: number;
  };
}

// =============================================
// Diagnostic Types
// =============================================

export interface DiagnosticRequest {
  image: string;
  resize?: boolean;
  run_ocr?: boolean;
  run_detection?: boolean;
}

export interface TimingStep {
  name: string;
  start_ms: number;
  end_ms: number;
  duration_ms: number;
  details: Record<string, unknown>;
}

export interface OCRDiagnosticResult {
  total_time_ms: number;
  text_region_count: number;
  timing_steps: TimingStep[];
  text_regions: TextRegion[];
  engine_info: Record<string, unknown>;
}

export interface DetectionDiagnosticResult {
  total_time_ms: number;
  element_count: number;
  timing_steps: TimingStep[];
  elements: UIElement[];
  model_info: Record<string, unknown>;
}

export interface DiagnosticResponse {
  analysis_id: string;
  timestamp: string;
  image_size: ImageSize;
  total_time_ms: number;
  preprocessing_time_ms: number;
  ocr_result: OCRDiagnosticResult | null;
  detection_result: DetectionDiagnosticResult | null;
  summary: Record<string, unknown>;
}
