/**
 * Side Panel Types
 */

export type PanelState = 'hidden' | 'expanded' | 'minimized';
export type DockedEdge = 'left' | 'right'; // Kept for API compatibility

export interface SidePanelState {
  state: PanelState;
  auto_minimize_enabled: boolean;
  target_pattern: string | null;
}

export interface SessionStartedPayload {
  session_id: string;
  query: string;
  total_steps: number;
  application_context: string | null;
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
 * Timing breakdown for CV analysis performance display.
 */
export interface TimingBreakdown {
  total_ms: number;
  preprocessing_ms: number;
  detection_ms: number;  // UI element detection (OmniParser/YOLO)
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

export interface StepChangedPayload {
  step_number: number;
  total_steps: number;
  instruction: string;
  detailed_instruction: string | null;
  action_type: string;
  target_label: string | null;
  confidence: number | null;
  // Timing breakdown for performance analysis
  timing?: TimingBreakdown | null;
}

export interface SessionEndedPayload {
  reason: 'completed' | 'abandoned' | 'error';
  message: string | null;
}

export interface StateChangedPayload {
  state: PanelState;
  previous_state: PanelState;
}

export interface CoordinatorStatusPayload {
  status: string;
  is_target_active: boolean;
  target_window: string | null;
}

// Event names matching Rust
export const PANEL_EVENTS = {
  SESSION_STARTED: 'panel:session_started',
  STEP_CHANGED: 'panel:step_changed',
  SESSION_ENDED: 'panel:session_ended',
  PANEL_READY: 'panel:ready',
  STATE_CHANGED: 'panel:state_changed',
  COORDINATOR_STATUS: 'panel:coordinator_status',
} as const;
