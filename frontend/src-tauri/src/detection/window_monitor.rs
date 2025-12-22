//! Active window monitoring for Windows.
//!
//! Provides functions to get the current foreground window title
//! and monitor for window changes matching specific patterns.

use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tokio::sync::mpsc;
use tokio::time::{interval, Duration};

/// Error type for window monitoring operations
#[derive(Debug, thiserror::Error)]
pub enum WindowMonitorError {
    #[error("Platform not supported")]
    UnsupportedPlatform,

    #[error("Failed to get window title: {0}")]
    GetTitleFailed(String),

    #[error("Monitor already running")]
    AlreadyRunning,
}

/// Information about the active window
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WindowInfo {
    pub title: String,
    pub process_name: Option<String>,
}

/// Gets the title of the currently active (foreground) window.
#[cfg(target_os = "windows")]
pub fn get_active_window_title() -> Result<WindowInfo, WindowMonitorError> {
    use windows::Win32::UI::WindowsAndMessaging::{GetForegroundWindow, GetWindowTextW};

    unsafe {
        let hwnd = GetForegroundWindow();
        let mut title_buf: [u16; 512] = [0; 512];
        let len = GetWindowTextW(hwnd, &mut title_buf);

        if len > 0 {
            let title = String::from_utf16_lossy(&title_buf[..len as usize]);
            Ok(WindowInfo {
                title,
                process_name: None, // Could be extended with process enumeration
            })
        } else {
            Ok(WindowInfo {
                title: String::new(),
                process_name: None,
            })
        }
    }
}

#[cfg(not(target_os = "windows"))]
pub fn get_active_window_title() -> Result<WindowInfo, WindowMonitorError> {
    // Placeholder for macOS/Linux - would need platform-specific implementation
    Err(WindowMonitorError::UnsupportedPlatform)
}

/// Pattern matching mode for window title detection
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum MatchMode {
    Contains,
    StartsWith,
    EndsWith,
    Exact,
    Regex,
}

impl Default for MatchMode {
    fn default() -> Self {
        MatchMode::Contains
    }
}

/// Pattern configuration for window matching
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WindowPattern {
    pub pattern: String,
    #[serde(default)]
    pub mode: MatchMode,
    #[serde(default)]
    pub case_sensitive: bool,
}

impl WindowPattern {
    /// Create a new pattern with default contains matching
    pub fn new(pattern: impl Into<String>) -> Self {
        Self {
            pattern: pattern.into(),
            mode: MatchMode::Contains,
            case_sensitive: false,
        }
    }

    /// Check if a window title matches this pattern
    pub fn matches(&self, title: &str) -> bool {
        let (pattern, title_cmp) = if self.case_sensitive {
            (self.pattern.clone(), title.to_string())
        } else {
            (self.pattern.to_lowercase(), title.to_lowercase())
        };

        match self.mode {
            MatchMode::Contains => title_cmp.contains(&pattern),
            MatchMode::StartsWith => title_cmp.starts_with(&pattern),
            MatchMode::EndsWith => title_cmp.ends_with(&pattern),
            MatchMode::Exact => title_cmp == pattern,
            MatchMode::Regex => {
                regex::Regex::new(&pattern)
                    .map(|re| re.is_match(&title_cmp))
                    .unwrap_or(false)
            }
        }
    }
}

/// Event emitted when a matching window is detected
#[derive(Debug, Clone, Serialize)]
pub struct WindowMatchEvent {
    pub window_info: WindowInfo,
    pub matched_pattern: String,
    pub timestamp: u64,
}

/// Handle to control the window monitor
pub struct MonitorHandle {
    stop_signal: Arc<AtomicBool>,
}

impl MonitorHandle {
    /// Stop the window monitoring
    pub fn stop(&self) {
        self.stop_signal.store(true, Ordering::SeqCst);
    }

    /// Check if monitoring is still active
    pub fn is_active(&self) -> bool {
        !self.stop_signal.load(Ordering::SeqCst)
    }
}

/// Starts monitoring for windows matching the given patterns.
///
/// Returns a channel receiver for match events and a handle to stop monitoring.
pub async fn start_monitoring(
    patterns: Vec<WindowPattern>,
    poll_interval_ms: u64,
) -> (mpsc::Receiver<WindowMatchEvent>, MonitorHandle) {
    let (tx, rx) = mpsc::channel(32);
    let stop_signal = Arc::new(AtomicBool::new(false));
    let handle = MonitorHandle {
        stop_signal: stop_signal.clone(),
    };

    tokio::spawn(async move {
        let mut interval = interval(Duration::from_millis(poll_interval_ms));
        let mut last_title = String::new();

        loop {
            interval.tick().await;

            if stop_signal.load(Ordering::SeqCst) {
                log::info!("Window monitoring stopped");
                break;
            }

            if let Ok(window_info) = get_active_window_title() {
                // Only process if title changed
                if window_info.title != last_title {
                    last_title = window_info.title.clone();

                    // Check patterns
                    for pattern in &patterns {
                        if pattern.matches(&window_info.title) {
                            let event = WindowMatchEvent {
                                window_info: window_info.clone(),
                                matched_pattern: pattern.pattern.clone(),
                                timestamp: std::time::SystemTime::now()
                                    .duration_since(std::time::UNIX_EPOCH)
                                    .unwrap_or_default()
                                    .as_secs(),
                            };

                            log::debug!("Window match: {} -> {}", window_info.title, pattern.pattern);

                            if tx.send(event).await.is_err() {
                                // Receiver dropped, stop monitoring
                                log::info!("Window monitor receiver dropped, stopping");
                                return;
                            }
                            break;
                        }
                    }
                }
            }
        }
    });

    (rx, handle)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pattern_contains() {
        let pattern = WindowPattern {
            pattern: "Chrome".to_string(),
            mode: MatchMode::Contains,
            case_sensitive: false,
        };

        assert!(pattern.matches("Google Chrome - Home"));
        assert!(pattern.matches("chrome browser"));
        assert!(!pattern.matches("Firefox Browser"));
    }

    #[test]
    fn test_pattern_starts_with() {
        let pattern = WindowPattern {
            pattern: "Visual Studio".to_string(),
            mode: MatchMode::StartsWith,
            case_sensitive: false,
        };

        assert!(pattern.matches("Visual Studio Code"));
        assert!(pattern.matches("visual studio 2022"));
        assert!(!pattern.matches("Microsoft Visual Studio"));
    }

    #[test]
    fn test_pattern_ends_with() {
        let pattern = WindowPattern {
            pattern: ".pdf".to_string(),
            mode: MatchMode::EndsWith,
            case_sensitive: false,
        };

        assert!(pattern.matches("Document.pdf"));
        assert!(pattern.matches("Report.PDF"));
        assert!(!pattern.matches("pdf viewer"));
    }

    #[test]
    fn test_pattern_case_sensitive() {
        let pattern = WindowPattern {
            pattern: "Chrome".to_string(),
            mode: MatchMode::Contains,
            case_sensitive: true,
        };

        assert!(pattern.matches("Google Chrome"));
        assert!(!pattern.matches("google chrome"));
    }
}
