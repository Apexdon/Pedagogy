//! Detection system modules.
//!
//! Provides screen capture and window monitoring functionality
//! for the Pedagogy desktop application.

pub mod screenshot;
pub mod window_monitor;
pub mod browser_detection;
pub mod browser_url;

// Re-export commonly used types
pub use screenshot::{CaptureResult, ScreenshotError};
pub use window_monitor::{WindowInfo, WindowPattern, MatchMode, WindowMatchEvent, WindowMonitorError};
pub use browser_detection::{
    ExtendedWindowInfo, BrowserType, is_browser_process,
    get_process_name_from_hwnd, get_extended_window_info_from_hwnd,
};
pub use browser_url::{
    get_browser_url_uia, extract_origin, extract_domain_from_url, url_matches_origin_pattern,
};
