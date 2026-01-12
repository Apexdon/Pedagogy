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

export interface StepChangedPayload {
  step_number: number;
  total_steps: number;
  instruction: string;
  detailed_instruction: string | null;
  action_type: string;
  target_label: string | null;
  confidence: number | null;
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
