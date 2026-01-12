/**
 * Halo Overlay API - Tauri commands for controlling the overlay window
 */

import { invoke } from '@tauri-apps/api/core';
import type { HaloTarget, BoundingBox, HaloStyle } from '../overlay/types';

export interface OverlayResponse {
  success: boolean;
  message: string;
}

export interface HaloState {
  target: HaloTarget | null;
  isVisible: boolean;
  targetWindow: string | null;
  isWindowMatch: boolean;
}

/**
 * Create the overlay window
 */
export async function createOverlayWindow(): Promise<OverlayResponse> {
  return invoke<OverlayResponse>('create_overlay_window');
}

/**
 * Destroy the overlay window
 */
export async function destroyOverlayWindow(): Promise<OverlayResponse> {
  return invoke<OverlayResponse>('destroy_overlay_window');
}

/**
 * Show a halo highlight at the specified position
 *
 * The Rust command expects a ShowHaloRequest with specific fields
 */
export async function showHalo(
  bounds: BoundingBox,
  style?: Partial<HaloStyle>,
  label?: string,
  stepNumber?: number,
  elementId?: string,
  instruction?: string,
  actionType?: string,
  elementType?: string
): Promise<OverlayResponse> {
  // Build the request object matching Rust's ShowHaloRequest struct
  const request = {
    target_id: elementId || `target-${Date.now()}`,
    bbox: {
      x1: bounds.x,
      y1: bounds.y,
      x2: bounds.x + bounds.width,
      y2: bounds.y + bounds.height,
    },
    element_type: elementType || 'interactive_element',
    label: label || null,
    step_number: stepNumber || 1,
    action_type: actionType || 'click',
    instruction: instruction || label || 'Follow the highlighted element',
    detailed_instruction: null,
    halo_style: style?.animation || 'pulse',
    confidence: 1.0,
  };

  return invoke<OverlayResponse>('show_halo', { request });
}

/**
 * Hide the current halo
 */
export async function hideHalo(): Promise<OverlayResponse> {
  return invoke<OverlayResponse>('hide_halo');
}

/**
 * Update the halo position/style
 *
 * The Rust command expects a ShowHaloRequest with specific fields
 */
export async function updateHalo(
  bounds: BoundingBox,
  style?: Partial<HaloStyle>,
  label?: string,
  stepNumber?: number,
  elementId?: string,
  instruction?: string,
  actionType?: string,
  elementType?: string
): Promise<OverlayResponse> {
  // Build the request object matching Rust's ShowHaloRequest struct
  const request = {
    target_id: elementId || `target-${Date.now()}`,
    bbox: {
      x1: bounds.x,
      y1: bounds.y,
      x2: bounds.x + bounds.width,
      y2: bounds.y + bounds.height,
    },
    element_type: elementType || 'interactive_element',
    label: label || null,
    step_number: stepNumber || 1,
    action_type: actionType || 'click',
    instruction: instruction || label || 'Follow the highlighted element',
    detailed_instruction: null,
    halo_style: style?.animation || 'pulse',
    confidence: 1.0,
  };

  return invoke<OverlayResponse>('update_halo', { request });
}

/**
 * Position the overlay over a specific window
 */
export async function positionOverlayOverWindow(
  windowTitle: string
): Promise<OverlayResponse> {
  return invoke<OverlayResponse>('position_overlay_over_window', {
    windowTitle,
  });
}

/**
 * Check if the overlay window is created
 */
export async function isOverlayCreated(): Promise<boolean> {
  return invoke<boolean>('is_overlay_created');
}

/**
 * Get the current halo state
 */
export async function getHaloState(): Promise<HaloState> {
  return invoke<HaloState>('get_halo_state');
}

/**
 * High-level helper: Show halo for a guidance step
 */
export async function showGuidanceStepHalo(
  bounds: BoundingBox,
  stepNumber: number,
  label: string,
  elementId?: string,
  instruction?: string,
  actionType?: string,
  elementType?: string
): Promise<OverlayResponse> {
  // Ensure overlay is created
  const created = await isOverlayCreated();
  if (!created) {
    await createOverlayWindow();
  }

  return showHalo(
    bounds,
    {
      color: 'blue',
      thickness: 3,
      animation: 'pulse',
      opacity: 1.0,
    },
    label,
    stepNumber,
    elementId,
    instruction || label,
    actionType || 'click',
    elementType || 'interactive_element'
  );
}

/**
 * High-level helper: Update halo for next guidance step
 */
export async function updateGuidanceStepHalo(
  bounds: BoundingBox,
  stepNumber: number,
  label: string,
  elementId?: string,
  instruction?: string,
  actionType?: string,
  elementType?: string
): Promise<OverlayResponse> {
  return updateHalo(
    bounds,
    {
      color: 'blue',
      thickness: 3,
      animation: 'pulse',
      opacity: 1.0,
    },
    label,
    stepNumber,
    elementId,
    instruction || label,
    actionType || 'click',
    elementType || 'interactive_element'
  );
}
