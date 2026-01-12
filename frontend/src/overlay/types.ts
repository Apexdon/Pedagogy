/**
 * Types for the Halo Overlay system
 *
 * NOTE: These types must match the Rust structs in src-tauri/src/overlay/halo.rs
 */

// Rust uses x1,y1,x2,y2 format
export interface RustBoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

// Convenience format for rendering
export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

// Convert from Rust bbox to rendering bbox
export function toRenderBounds(bbox: RustBoundingBox): BoundingBox {
  return {
    x: bbox.x1,
    y: bbox.y1,
    width: bbox.x2 - bbox.x1,
    height: bbox.y2 - bbox.y1,
  };
}

export type HaloStyleType = 'glow' | 'pulse' | 'outline' | 'arrow';
export type HaloColor = 'blue' | 'green' | 'yellow' | 'red' | 'purple';

export interface HaloStyle {
  color: HaloColor;
  thickness: number;
  animation: HaloStyleType;
  opacity: number;
}

/**
 * HaloTarget - matches Rust struct in halo.rs
 */
export interface HaloTarget {
  target_id: string;
  bbox: RustBoundingBox;
  element_type: string;
  label: string | null;
  step_number: number;
  action_type: string;
  instruction: string;
  detailed_instruction: string | null;
  halo_style: HaloStyleType;
  confidence: number;
}

export interface HaloEventPayload {
  target: HaloTarget | null;
  visible: boolean;
  window_title: string | null;
}

// Event names matching Rust constants
export const HALO_EVENTS = {
  SHOW: 'halo:show',
  HIDE: 'halo:hide',
  UPDATE: 'halo:update',
  READY: 'halo:ready',
} as const;
