//! Detection system modules.
//!
//! Provides screen capture and window monitoring functionality
//! for the Pedagogy desktop application.

pub mod screenshot;
pub mod window_monitor;

// Re-export commonly used types
pub use screenshot::{CaptureResult, ScreenshotError};
pub use window_monitor::{WindowInfo, WindowPattern, MatchMode, WindowMatchEvent, WindowMonitorError};
