//! Halo Overlay Module
//!
//! This module provides functionality for creating and managing
//! a transparent overlay window that displays halo highlights
//! on target UI elements.

pub mod halo;
pub mod window;

pub use halo::{BoundingBox, HaloStyle, HaloTarget};
pub use window::{OverlayManager, OverlayError};
