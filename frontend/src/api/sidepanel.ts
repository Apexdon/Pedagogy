/**
 * Side Panel API - Tauri commands for controlling the side panel window
 */

import { invoke } from '@tauri-apps/api/core';
import type { SidePanelState, DockedEdge, TimingBreakdown } from '../sidepanel/types';

export interface SidePanelResponse {
  success: boolean;
  message: string;
}

/**
 * Create the side panel window
 */
export async function createSidePanelWindow(): Promise<SidePanelResponse> {
  return invoke<SidePanelResponse>('create_sidepanel_window');
}

/**
 * Destroy the side panel window
 */
export async function destroySidePanelWindow(): Promise<SidePanelResponse> {
  return invoke<SidePanelResponse>('destroy_sidepanel_window');
}

/**
 * Expand the side panel
 */
export async function expandSidePanel(): Promise<SidePanelResponse> {
  return invoke<SidePanelResponse>('expand_sidepanel');
}

/**
 * Minimize the side panel
 */
export async function minimizeSidePanel(): Promise<SidePanelResponse> {
  return invoke<SidePanelResponse>('minimize_sidepanel');
}

/**
 * Toggle the side panel between expanded and minimized
 */
export async function toggleSidePanel(): Promise<SidePanelResponse> {
  return invoke<SidePanelResponse>('toggle_sidepanel');
}

/**
 * Hide the side panel completely
 */
export async function hideSidePanel(): Promise<SidePanelResponse> {
  return invoke<SidePanelResponse>('hide_sidepanel');
}

/**
 * Set the docked edge (left or right)
 */
export async function setSidePanelEdge(edge: DockedEdge): Promise<SidePanelResponse> {
  return invoke<SidePanelResponse>('set_sidepanel_edge', { edge });
}

/**
 * Set the vertical position
 */
export async function setSidePanelPosition(y: number): Promise<SidePanelResponse> {
  return invoke<SidePanelResponse>('set_sidepanel_position', { y });
}

/**
 * Set auto-minimize enabled/disabled
 */
export async function setSidePanelAutoMinimize(enabled: boolean): Promise<SidePanelResponse> {
  return invoke<SidePanelResponse>('set_sidepanel_auto_minimize', { enabled });
}

/**
 * Set the target window pattern for auto-minimize
 */
export async function setSidePanelTargetPattern(pattern: string | null): Promise<SidePanelResponse> {
  return invoke<SidePanelResponse>('set_sidepanel_target_pattern', { pattern });
}

/**
 * Check if the side panel window is created
 */
export async function isSidePanelCreated(): Promise<boolean> {
  return invoke<boolean>('is_sidepanel_created');
}

/**
 * Get the current side panel state
 */
export async function getSidePanelState(): Promise<SidePanelState> {
  return invoke<SidePanelState>('get_sidepanel_state');
}

/**
 * Notify panel of session started
 */
export async function notifyPanelSessionStarted(
  sessionId: string,
  query: string,
  totalSteps: number,
  applicationContext: string | null = null
): Promise<SidePanelResponse> {
  return invoke<SidePanelResponse>('notify_panel_session_started', {
    session_id: sessionId,
    query,
    total_steps: totalSteps,
    application_context: applicationContext,
  });
}

/**
 * Notify panel of step changed
 */
export async function notifyPanelStepChanged(
  stepNumber: number,
  totalSteps: number,
  instruction: string,
  detailedInstruction: string | null = null,
  actionType: string = 'click',
  targetLabel: string | null = null,
  confidence: number | null = null,
  timing: TimingBreakdown | null = null
): Promise<SidePanelResponse> {
  return invoke<SidePanelResponse>('notify_panel_step_changed', {
    step_number: stepNumber,
    total_steps: totalSteps,
    instruction,
    detailed_instruction: detailedInstruction,
    action_type: actionType,
    target_label: targetLabel,
    confidence,
    timing,
  });
}

/**
 * Notify panel of session ended
 */
export async function notifyPanelSessionEnded(
  reason: 'completed' | 'abandoned' | 'error',
  message: string | null = null
): Promise<SidePanelResponse> {
  return invoke<SidePanelResponse>('notify_panel_session_ended', {
    reason,
    message,
  });
}

/**
 * Notify panel of coordinator status change
 */
export async function notifyPanelCoordinatorStatus(
  status: string,
  isTargetActive: boolean,
  targetWindow: string | null = null
): Promise<SidePanelResponse> {
  return invoke<SidePanelResponse>('notify_panel_coordinator_status', {
    status,
    is_target_active: isTargetActive,
    target_window: targetWindow,
  });
}

/**
 * High-level helper: Show and expand the side panel for a guidance session
 */
export async function showGuidancePanel(
  sessionId: string,
  query: string,
  totalSteps: number,
  applicationContext: string | null = null
): Promise<void> {
  // Ensure panel is created
  const created = await isSidePanelCreated();
  if (!created) {
    await createSidePanelWindow();
  }

  // Expand the panel
  await expandSidePanel();

  // Notify of session start
  await notifyPanelSessionStarted(sessionId, query, totalSteps, applicationContext);
}

/**
 * High-level helper: Update panel with current step
 */
export async function updateGuidancePanel(
  stepNumber: number,
  totalSteps: number,
  instruction: string,
  detailedInstruction: string | null = null,
  actionType: string = 'click',
  targetLabel: string | null = null,
  confidence: number | null = null,
  timing: TimingBreakdown | null = null
): Promise<void> {
  await notifyPanelStepChanged(
    stepNumber,
    totalSteps,
    instruction,
    detailedInstruction,
    actionType,
    targetLabel,
    confidence,
    timing
  );
}

/**
 * High-level helper: Close the guidance panel
 */
export async function closeGuidancePanel(
  reason: 'completed' | 'abandoned' | 'error' = 'completed',
  message: string | null = null
): Promise<void> {
  await notifyPanelSessionEnded(reason, message);
  await hideSidePanel();
}
