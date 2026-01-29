//! Tauri commands for detection functionality.
//!
//! These commands are exposed to the frontend via invoke().

use crate::detection::{
    screenshot, window_monitor, browser_detection, CaptureResult, WindowInfo, WindowPattern,
    ExtendedWindowInfo, BrowserType,
};
use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use tauri::{Emitter, State};

/// State for managing detection features
pub struct DetectionState {
    pub is_monitoring: Mutex<bool>,
}

impl Default for DetectionState {
    fn default() -> Self {
        Self {
            is_monitoring: Mutex::new(false),
        }
    }
}

// Make DetectionState clonable for async operations
impl Clone for DetectionState {
    fn clone(&self) -> Self {
        Self {
            is_monitoring: Mutex::new(
                *self.is_monitoring.lock().unwrap_or_else(|e| e.into_inner())
            ),
        }
    }
}

/// Response from capture commands
#[derive(Debug, Serialize)]
pub struct CaptureResponse {
    pub success: bool,
    #[serde(flatten)]
    pub result: Option<CaptureResult>,
    pub error: Option<String>,
}

/// Captures the primary screen at full resolution.
///
/// Returns Base64 encoded PNG suitable for CV analysis.
#[tauri::command]
pub async fn capture_screenshot() -> Result<CaptureResponse, String> {
    log::info!("Capturing screenshot...");

    match screenshot::capture_primary() {
        Ok(result) => {
            log::info!(
                "Screenshot captured: {}x{} from {}",
                result.width,
                result.height,
                result.monitor_name
            );
            Ok(CaptureResponse {
                success: true,
                result: Some(result),
                error: None,
            })
        }
        Err(e) => {
            log::error!("Screenshot capture failed: {}", e);
            Ok(CaptureResponse {
                success: false,
                result: None,
                error: Some(e.to_string()),
            })
        }
    }
}

/// Captures the screen at reduced resolution for faster processing.
#[tauri::command]
pub async fn capture_screenshot_low_res(
    max_width: Option<u32>,
    max_height: Option<u32>,
) -> Result<CaptureResponse, String> {
    let width = max_width.unwrap_or(854);
    let height = max_height.unwrap_or(480);

    log::info!("Capturing low-res screenshot (max {}x{})...", width, height);

    match screenshot::capture_low_res(width, height) {
        Ok(result) => {
            log::info!(
                "Low-res screenshot captured: {}x{}",
                result.width,
                result.height
            );
            Ok(CaptureResponse {
                success: true,
                result: Some(result),
                error: None,
            })
        }
        Err(e) => {
            log::error!("Low-res screenshot capture failed: {}", e);
            Ok(CaptureResponse {
                success: false,
                result: None,
                error: Some(e.to_string()),
            })
        }
    }
}

/// Captures a specific region of the screen.
#[tauri::command]
pub async fn capture_screenshot_region(
    x: i32,
    y: i32,
    width: u32,
    height: u32,
) -> Result<CaptureResponse, String> {
    log::info!("Capturing screenshot region: {}x{} at ({}, {})", width, height, x, y);

    match screenshot::capture_region(x, y, width, height) {
        Ok(result) => {
            log::info!("Region screenshot captured: {}x{}", result.width, result.height);
            Ok(CaptureResponse {
                success: true,
                result: Some(result),
                error: None,
            })
        }
        Err(e) => {
            log::error!("Region screenshot capture failed: {}", e);
            Ok(CaptureResponse {
                success: false,
                result: None,
                error: Some(e.to_string()),
            })
        }
    }
}

/// Captures a specific window by its title pattern.
///
/// Uses case-insensitive contains matching to find the window.
#[tauri::command]
pub async fn capture_window(
    title_pattern: String,
) -> Result<CaptureResponse, String> {
    log::info!("Capturing window matching '{}'...", title_pattern);

    match screenshot::capture_window_by_title(&title_pattern) {
        Ok(result) => {
            log::info!(
                "Window captured: {}x{} - '{}'",
                result.width,
                result.height,
                result.monitor_name
            );
            Ok(CaptureResponse {
                success: true,
                result: Some(result),
                error: None,
            })
        }
        Err(e) => {
            log::error!("Window capture failed: {}", e);
            Ok(CaptureResponse {
                success: false,
                result: None,
                error: Some(e.to_string()),
            })
        }
    }
}

/// Captures a specific window by its HWND (window handle).
///
/// This is more efficient than title matching when the HWND is already known,
/// such as after a successful URL-based browser detection.
#[tauri::command]
pub async fn capture_window_by_hwnd(
    hwnd: i64,
) -> Result<CaptureResponse, String> {
    log::info!("Capturing window by HWND: {}...", hwnd);

    match screenshot::capture_window_by_hwnd(hwnd as isize) {
        Ok(result) => {
            log::info!(
                "Window captured: {}x{} - '{}'",
                result.width,
                result.height,
                result.monitor_name
            );
            Ok(CaptureResponse {
                success: true,
                result: Some(result),
                error: None,
            })
        }
        Err(e) => {
            log::error!("Window capture by HWND failed: {}", e);
            Ok(CaptureResponse {
                success: false,
                result: None,
                error: Some(e.to_string()),
            })
        }
    }
}

/// Gets the title of the currently active window.
#[tauri::command]
pub fn get_active_window_title() -> Result<WindowInfo, String> {
    window_monitor::get_active_window_title()
        .map_err(|e| e.to_string())
}

/// Request to start window monitoring
#[derive(Debug, Deserialize)]
pub struct StartMonitoringRequest {
    pub patterns: Vec<WindowPattern>,
    #[serde(default = "default_poll_interval")]
    pub poll_interval_ms: u64,
}

fn default_poll_interval() -> u64 {
    500
}

/// Starts monitoring for windows matching specified patterns.
///
/// Emits 'window-match' events to the frontend when matches are found.
#[tauri::command]
pub async fn start_window_monitoring(
    app: tauri::AppHandle,
    state: State<'_, DetectionState>,
    request: StartMonitoringRequest,
) -> Result<(), String> {
    // Check and update monitoring state in a scoped block to release lock before await
    {
        let mut is_monitoring = state.is_monitoring.lock().map_err(|e| e.to_string())?;

        if *is_monitoring {
            return Err("Window monitoring is already active".to_string());
        }

        *is_monitoring = true;
    } // Lock is released here

    log::info!(
        "Starting window monitoring with {} patterns",
        request.patterns.len()
    );

    let (mut rx, _handle) = window_monitor::start_monitoring(
        request.patterns,
        request.poll_interval_ms,
    )
    .await;

    // Spawn task to forward events to frontend
    let app_handle = app.clone();

    tokio::spawn(async move {
        while let Some(event) = rx.recv().await {
            log::debug!("Window match event: {:?}", event);
            // Emit event to frontend
            if let Err(e) = app_handle.emit("window-match", &event) {
                log::error!("Failed to emit window-match event: {}", e);
            }
        }
        log::info!("Window monitoring task ended");
    });

    Ok(())
}

/// Stops window monitoring.
#[tauri::command]
pub fn stop_window_monitoring(
    state: State<'_, DetectionState>,
) -> Result<(), String> {
    let mut is_monitoring = state.is_monitoring.lock().map_err(|e| e.to_string())?;
    *is_monitoring = false;
    log::info!("Window monitoring stopped");
    Ok(())
}

/// Checks if window monitoring is active.
#[tauri::command]
pub fn is_window_monitoring_active(
    state: State<'_, DetectionState>,
) -> Result<bool, String> {
    let is_monitoring = state.is_monitoring.lock().map_err(|e| e.to_string())?;
    Ok(*is_monitoring)
}

/// Gets information about available monitors
#[tauri::command]
pub fn get_monitors() -> Result<Vec<MonitorInfo>, String> {
    use xcap::Monitor;

    let monitors = Monitor::all().map_err(|e| e.to_string())?;

    Ok(monitors
        .iter()
        .map(|m| MonitorInfo {
            name: m.name().to_string(),
            is_primary: m.is_primary(),
            width: m.width(),
            height: m.height(),
            x: m.x(),
            y: m.y(),
        })
        .collect())
}

/// Information about a monitor
#[derive(Debug, Serialize)]
pub struct MonitorInfo {
    pub name: String,
    pub is_primary: bool,
    pub width: u32,
    pub height: u32,
    pub x: i32,
    pub y: i32,
}

// =============================================
// Smart Window Detection Commands (Phase 8)
// =============================================

/// Match mode for smart window detection
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum SmartMatchMode {
    Url,      // Match by browser URL (for websites)
    Process,  // Match by process name (for desktop apps)
    Title,    // Match by window title (legacy)
    Auto,     // Auto-detect: try URL first (if browser), then process, then title
}

impl Default for SmartMatchMode {
    fn default() -> Self {
        SmartMatchMode::Auto
    }
}

/// Configuration for smart window matching
#[derive(Debug, Clone, Deserialize)]
pub struct SmartMatchConfig {
    /// Matching mode
    #[serde(default)]
    pub mode: SmartMatchMode,

    /// URL patterns for website matching (e.g., "rs-online.com", "*.salesforce.com")
    pub url_patterns: Option<Vec<String>>,

    /// Process name for desktop app matching (e.g., "Code.exe")
    pub process_name: Option<String>,

    /// Window title pattern (legacy, for title matching)
    pub title_pattern: Option<String>,
}

/// Result of smart window matching
#[derive(Debug, Serialize)]
pub struct SmartMatchResult {
    pub matched: bool,
    pub match_mode_used: String,
    pub window_info: Option<ExtendedWindowInfo>,
    pub matched_pattern: Option<String>,
    pub debug_info: SmartMatchDebugInfo,
    /// Window handle for caching (raw pointer as isize for serialization)
    pub hwnd: Option<isize>,
}

/// Debug information for smart matching
#[derive(Debug, Serialize)]
pub struct SmartMatchDebugInfo {
    pub window_title: String,
    pub process_name: Option<String>,
    pub is_browser: bool,
    pub browser_type: Option<String>,
    pub detected_url: Option<String>,
    pub detected_domain: Option<String>,
}

/// Gets extended window information including URL for browsers.
///
/// This command retrieves detailed information about the foreground window,
/// including browser URL extraction using Windows UI Automation.
#[tauri::command]
pub fn get_extended_window_info() -> Result<Option<ExtendedWindowInfo>, String> {
    log::info!("Getting extended window info...");

    #[cfg(target_os = "windows")]
    {
        let info = browser_detection::get_extended_window_info();
        if let Some(ref info) = info {
            log::info!(
                "Extended window info: title='{}', process='{}', is_browser={}, url={:?}",
                info.title,
                info.process_name,
                info.is_browser,
                info.url
            );
        }
        Ok(info)
    }

    #[cfg(not(target_os = "windows"))]
    {
        log::warn!("Extended window info not supported on this platform");
        Ok(None)
    }
}

/// Simple foreground window info for visual verification approach.
/// Returns minimal info about the foreground window (HWND, title, process).
/// The backend will verify if this is the target app using OCR on the screenshot.
#[derive(Debug, Serialize)]
pub struct ForegroundWindowInfo {
    /// Window handle as isize for caching/comparison
    pub hwnd: isize,
    /// Window title
    pub title: String,
    /// Process name (e.g., "chrome.exe", "msedge.exe")
    pub process_name: String,
    /// Whether this appears to be a browser window
    pub is_browser: bool,
}

/// Gets simple foreground window info for visual verification.
/// This is a lightweight command that just returns the foreground window's
/// HWND, title, and process name. The backend will verify if this is the
/// target application using OCR-based brand keyword matching on the screenshot.
#[tauri::command]
pub fn get_foreground_window_simple() -> Result<Option<ForegroundWindowInfo>, String> {
    log::info!("Getting foreground window info (simple)...");

    #[cfg(target_os = "windows")]
    {
        use windows::Win32::UI::WindowsAndMessaging::{GetForegroundWindow, GetWindowTextW};
        use crate::detection::browser_detection::{get_process_name_from_hwnd, is_browser_process};

        unsafe {
            let hwnd = GetForegroundWindow();
            if hwnd.0.is_null() {
                log::warn!("No foreground window found");
                return Ok(None);
            }

            // Get window title
            let mut title_buf: [u16; 512] = [0; 512];
            let len = GetWindowTextW(hwnd, &mut title_buf);
            let title = if len > 0 {
                String::from_utf16_lossy(&title_buf[..len as usize])
            } else {
                String::new()
            };

            // Get process name
            let process_name = get_process_name_from_hwnd(hwnd)
                .unwrap_or_else(|| "unknown".to_string());

            let is_browser = is_browser_process(&process_name);

            log::info!("Foreground window: '{}' (process: {}, browser: {})",
                title, process_name, is_browser);

            Ok(Some(ForegroundWindowInfo {
                hwnd: hwnd.0 as isize,
                title,
                process_name,
                is_browser,
            }))
        }
    }

    #[cfg(not(target_os = "windows"))]
    {
        log::warn!("Foreground window info not supported on this platform");
        Ok(None)
    }
}

/// Lists all open browser windows for debugging purposes.
/// Returns a list of browser window titles and process names.
#[tauri::command]
pub fn list_browser_windows() -> Result<Vec<BrowserWindowDebugInfo>, String> {
    log::info!("Listing all browser windows for debugging...");

    #[cfg(target_os = "windows")]
    {
        use windows::Win32::UI::WindowsAndMessaging::{
            GetDesktopWindow, GetWindow, IsWindowVisible, GetWindowTextW, GW_CHILD, GW_HWNDNEXT,
        };
        use crate::detection::browser_detection::{
            is_browser_process, get_process_name_from_hwnd,
        };

        let mut browsers = Vec::new();

        unsafe {
            let desktop = GetDesktopWindow();
            let first_child = match GetWindow(desktop, GW_CHILD) {
                Ok(h) => h,
                Err(e) => {
                    log::warn!("Failed to get first child window: {:?}", e);
                    return Ok(browsers);
                }
            };

            if first_child.0.is_null() {
                return Ok(browsers);
            }

            let mut hwnd = first_child;

            loop {
                if IsWindowVisible(hwnd).as_bool() {
                    let mut title_buf: [u16; 512] = [0; 512];
                    let len = GetWindowTextW(hwnd, &mut title_buf);

                    if len > 0 {
                        let title = String::from_utf16_lossy(&title_buf[..len as usize]);

                        if let Some(process_name) = get_process_name_from_hwnd(hwnd) {
                            if is_browser_process(&process_name) {
                                log::info!("Found browser: '{}' ({})", title, process_name);
                                browsers.push(BrowserWindowDebugInfo {
                                    title: title.clone(),
                                    process_name: process_name.clone(),
                                });
                            }
                        }
                    }
                }

                match GetWindow(hwnd, GW_HWNDNEXT) {
                    Ok(next) if !next.0.is_null() => hwnd = next,
                    _ => break,
                }
            }
        }

        log::info!("Found {} browser windows total", browsers.len());
        Ok(browsers)
    }

    #[cfg(not(target_os = "windows"))]
    {
        Ok(Vec::new())
    }
}

/// Debug info for a browser window
#[derive(Debug, Serialize)]
pub struct BrowserWindowDebugInfo {
    pub title: String,
    pub process_name: String,
}

/// Debug command to list all visible windows and their process names
/// This helps diagnose why browser windows aren't being detected
#[tauri::command]
pub fn debug_list_windows() -> Result<Vec<BrowserWindowDebugInfo>, String> {
    #[cfg(target_os = "windows")]
    {
        use windows::Win32::UI::WindowsAndMessaging::{
            GetDesktopWindow, GetWindow, IsWindowVisible, GetWindowTextW, GW_CHILD, GW_HWNDNEXT,
        };
        use crate::detection::browser_detection::{get_process_name_from_hwnd, is_browser_process};

        let mut windows = Vec::new();

        unsafe {
            let desktop = GetDesktopWindow();
            let first_child = match GetWindow(desktop, GW_CHILD) {
                Ok(h) => h,
                Err(e) => return Err(format!("Failed to get first child: {:?}", e)),
            };

            if first_child.0.is_null() {
                return Ok(windows);
            }

            let mut hwnd = first_child;
            let mut count = 0;

            loop {
                if IsWindowVisible(hwnd).as_bool() {
                    let mut title_buf: [u16; 512] = [0; 512];
                    let len = GetWindowTextW(hwnd, &mut title_buf);
                    let title = if len > 0 {
                        String::from_utf16_lossy(&title_buf[..len as usize])
                    } else {
                        String::new()
                    };

                    // Only include windows with titles
                    if !title.is_empty() {
                        let process_name = get_process_name_from_hwnd(hwnd)
                            .unwrap_or_else(|| "UNKNOWN".to_string());

                        let is_browser = is_browser_process(&process_name);

                        // Log all browser windows
                        if is_browser {
                            log::info!("BROWSER WINDOW: '{}' (process: {})", title, process_name);
                        }

                        windows.push(BrowserWindowDebugInfo {
                            title: format!("{} [browser={}]", title, is_browser),
                            process_name,
                        });

                        count += 1;
                        if count >= 50 {
                            break; // Limit to first 50 windows
                        }
                    }
                }

                match GetWindow(hwnd, GW_HWNDNEXT) {
                    Ok(next) if !next.0.is_null() => hwnd = next,
                    _ => break,
                }
            }
        }

        Ok(windows)
    }

    #[cfg(not(target_os = "windows"))]
    {
        Ok(vec![])
    }
}

/// Performs smart window matching using multiple strategies.
///
/// This is the main command for smart target application detection.
/// It tries different matching strategies based on the configured mode:
/// - URL: Match browser URL against patterns (best for websites)
/// - Process: Match process name (best for desktop apps)
/// - Title: Match window title (legacy fallback)
/// - Auto: Try all strategies in order (URL -> Process -> Title)
///
/// For URL matching, this searches ALL open browser windows, not just the foreground window.
/// This allows guidance to continue working even when the Pedagogy app is in focus.
#[tauri::command]
pub fn smart_match_window(config: SmartMatchConfig) -> Result<SmartMatchResult, String> {
    log::info!("Performing smart window match with mode: {:?}", config.mode);

    #[cfg(target_os = "windows")]
    {
        // MATCHING STRATEGY FOR BROWSERS:
        // 1. Try origin-based matching using new uiautomation crate (most reliable)
        // 2. Fall back to domain keyword matching in window titles
        // 3. Fall back to explicit title pattern matching

        if let Some(ref url_patterns) = config.url_patterns {
            if !url_patterns.is_empty() && matches!(config.mode, SmartMatchMode::Url | SmartMatchMode::Auto) {
                log::info!("URL patterns provided: {:?}", url_patterns);

                // STRATEGY 1: Try origin-based matching (most reliable)
                // This uses the new uiautomation crate to extract actual URLs from browser address bars
                if let Some(info) = find_browser_window_by_origin(url_patterns) {
                    log::info!("Found matching browser window via origin: {} (origin: {:?})",
                        info.title, info.url_origin);

                    let debug_info = SmartMatchDebugInfo {
                        window_title: info.title.clone(),
                        process_name: Some(info.process_name.clone()),
                        is_browser: info.is_browser,
                        browser_type: info.browser_type.as_ref().map(|bt| format!("{:?}", bt)),
                        detected_url: info.url.clone(),
                        detected_domain: info.url_domain.clone(),
                    };

                    return Ok(SmartMatchResult {
                        matched: true,
                        match_mode_used: "origin".to_string(),
                        window_info: Some(info.clone()),
                        matched_pattern: info.url_origin.or(info.url_domain),
                        debug_info,
                        hwnd: Some(info.hwnd as isize),
                    });
                }

                log::info!("Origin matching failed, trying domain keyword matching in titles");

                // STRATEGY 2: Fall back to domain keyword matching in titles
                let title_keywords = extract_title_keywords_from_url_patterns(&config.url_patterns);

                if !title_keywords.is_empty() {
                    log::info!("Searching browser windows using title keywords: {:?}", title_keywords);

                    if let Some(info) = find_browser_window_by_domain_keywords(&title_keywords) {
                        log::info!("Found matching browser window via domain keyword in title: {}",
                            info.title);

                        let debug_info = SmartMatchDebugInfo {
                            window_title: info.title.clone(),
                            process_name: Some(info.process_name.clone()),
                            is_browser: info.is_browser,
                            browser_type: info.browser_type.as_ref().map(|bt| format!("{:?}", bt)),
                            detected_url: info.url.clone(),
                            detected_domain: info.url_domain.clone(),
                        };

                        return Ok(SmartMatchResult {
                            matched: true,
                            match_mode_used: "title_domain".to_string(),
                            window_info: Some(info.clone()),
                            matched_pattern: Some(title_keywords.join(", ")),
                            debug_info,
                            hwnd: Some(info.hwnd as isize),
                        });
                    }
                }

                // STRATEGY 3: Try explicit title pattern if provided
                if let Some(ref title_pattern) = config.title_pattern {
                    if let Some(info) = find_browser_window_by_title(title_pattern) {
                        log::info!("Found matching browser window via explicit title pattern: {}", info.title);

                        let debug_info = SmartMatchDebugInfo {
                            window_title: info.title.clone(),
                            process_name: Some(info.process_name.clone()),
                            is_browser: info.is_browser,
                            browser_type: info.browser_type.as_ref().map(|bt| format!("{:?}", bt)),
                            detected_url: info.url.clone(),
                            detected_domain: info.url_domain.clone(),
                        };

                        return Ok(SmartMatchResult {
                            matched: true,
                            match_mode_used: "title".to_string(),
                            window_info: Some(info.clone()),
                            matched_pattern: Some(title_pattern.clone()),
                            debug_info,
                            hwnd: Some(info.hwnd as isize),
                        });
                    }
                }

                // No match found in any browser window
                log::info!("No browser window found matching any strategy");
                return Ok(SmartMatchResult {
                    matched: false,
                    match_mode_used: "origin".to_string(),
                    window_info: None,
                    matched_pattern: None,
                    debug_info: SmartMatchDebugInfo {
                        window_title: String::new(),
                        process_name: None,
                        is_browser: false,
                        browser_type: None,
                        detected_url: None,
                        detected_domain: None,
                    },
                    hwnd: None,
                });
            }
        }

        // For non-URL matching modes, use the foreground window
        let window_info = browser_detection::get_extended_window_info();

        if window_info.is_none() {
            return Ok(SmartMatchResult {
                matched: false,
                match_mode_used: "none".to_string(),
                window_info: None,
                matched_pattern: None,
                debug_info: SmartMatchDebugInfo {
                    window_title: String::new(),
                    process_name: None,
                    is_browser: false,
                    browser_type: None,
                    detected_url: None,
                    detected_domain: None,
                },
                hwnd: None,
            });
        }

        let info = window_info.unwrap();

        // Build debug info
        let debug_info = SmartMatchDebugInfo {
            window_title: info.title.clone(),
            process_name: Some(info.process_name.clone()),
            is_browser: info.is_browser,
            browser_type: info.browser_type.as_ref().map(|bt| format!("{:?}", bt)),
            detected_url: info.url.clone(),
            detected_domain: info.url_domain.clone(),
        };

        // Try matching based on mode
        let (matched, mode_used, pattern) = match config.mode {
            SmartMatchMode::Url => {
                try_url_match(&info, &config.url_patterns)
            }
            SmartMatchMode::Process => {
                try_process_match(&info, &config.process_name)
            }
            SmartMatchMode::Title => {
                try_title_match(&info, &config.title_pattern)
            }
            SmartMatchMode::Auto => {
                // Auto mode: different strategies for browsers vs desktop apps
                // For browsers: URL matching is primary, skip title matching entirely
                // For desktop apps: process matching, then title matching

                if info.is_browser {
                    // Browser detected - use URL matching ONLY
                    // Don't fall back to title matching because browser titles change per page
                    log::info!("Browser detected, using URL-only matching strategy");

                    let (matched, mode, pattern) = try_url_match(&info, &config.url_patterns);
                    if matched {
                        return Ok(SmartMatchResult {
                            matched: true,
                            match_mode_used: mode,
                            window_info: Some(info.clone()),
                            matched_pattern: Some(pattern),
                            debug_info,
                            hwnd: Some(info.hwnd as isize),
                        });
                    }

                    // For browsers, if URL doesn't match, return no match
                    // Don't try title matching - it's unreliable for web apps
                    log::info!("Browser URL did not match configured patterns");
                    (false, "url".to_string(), String::new())
                } else {
                    // Non-browser (desktop app) - try process then title
                    log::info!("Non-browser window, using process/title matching strategy");

                    // 1. Try process match
                    let (matched, mode, pattern) = try_process_match(&info, &config.process_name);
                    if matched {
                        return Ok(SmartMatchResult {
                            matched: true,
                            match_mode_used: mode,
                            window_info: Some(info.clone()),
                            matched_pattern: Some(pattern),
                            debug_info,
                            hwnd: Some(info.hwnd as isize),
                        });
                    }

                    // 2. Try title match as fallback for desktop apps only
                    try_title_match(&info, &config.title_pattern)
                }
            }
        };

        let hwnd_value = if matched { Some(info.hwnd as isize) } else { None };
        Ok(SmartMatchResult {
            matched,
            match_mode_used: mode_used,
            window_info: if matched { Some(info) } else { None },
            matched_pattern: if matched { Some(pattern) } else { None },
            debug_info,
            hwnd: hwnd_value,
        })
    }

    #[cfg(not(target_os = "windows"))]
    {
        log::warn!("Smart window matching not supported on this platform");
        Ok(SmartMatchResult {
            matched: false,
            match_mode_used: "unsupported".to_string(),
            window_info: None,
            matched_pattern: None,
            debug_info: SmartMatchDebugInfo {
                window_title: String::new(),
                process_name: None,
                is_browser: false,
                browser_type: None,
                detected_url: None,
                detected_domain: None,
            },
            hwnd: None,
        })
    }
}

#[cfg(target_os = "windows")]
fn try_url_match(
    info: &ExtendedWindowInfo,
    url_patterns: &Option<Vec<String>>,
) -> (bool, String, String) {
    if let Some(patterns) = url_patterns {
        for pattern in patterns {
            if info.url_matches_pattern(pattern) {
                log::info!("URL match found: {} matches pattern '{}'",
                    info.url_domain.as_deref().unwrap_or("unknown"), pattern);
                return (true, "url".to_string(), pattern.clone());
            }
        }
    }
    (false, "url".to_string(), String::new())
}

#[cfg(target_os = "windows")]
fn try_process_match(
    info: &ExtendedWindowInfo,
    process_name: &Option<String>,
) -> (bool, String, String) {
    if let Some(target_process) = process_name {
        let current_process = info.process_name.to_lowercase();
        let target = target_process.to_lowercase();

        if current_process == target || current_process.contains(&target) {
            log::info!("Process match found: {} matches '{}'", info.process_name, target_process);
            return (true, "process".to_string(), target_process.clone());
        }
    }
    (false, "process".to_string(), String::new())
}

#[cfg(target_os = "windows")]
fn try_title_match(
    info: &ExtendedWindowInfo,
    title_pattern: &Option<String>,
) -> (bool, String, String) {
    if let Some(pattern) = title_pattern {
        let title_lower = info.title.to_lowercase();
        let pattern_lower = pattern.to_lowercase();

        // Handle wildcard patterns like "*rs-online*"
        let clean_pattern = pattern_lower
            .trim_start_matches('*')
            .trim_end_matches('*');

        if title_lower.contains(clean_pattern) {
            log::info!("Title match found: '{}' contains '{}'", info.title, pattern);
            return (true, "title".to_string(), pattern.clone());
        }
    }
    (false, "title".to_string(), String::new())
}

/// Find any browser window matching the given title pattern
/// This searches all open windows, not just the foreground window
/// Uses GetWindow to iterate through windows (more reliable than EnumWindows callbacks)
#[cfg(target_os = "windows")]
fn find_browser_window_by_title(title_pattern: &str) -> Option<ExtendedWindowInfo> {
    use windows::Win32::UI::WindowsAndMessaging::{
        GetDesktopWindow, GetWindow, IsWindowVisible, GetWindowTextW, GW_CHILD, GW_HWNDNEXT,
    };
    use crate::detection::browser_detection::{
        is_browser_process, get_process_name_from_hwnd, get_extended_window_info_from_hwnd,
    };

    let pattern = title_pattern.to_lowercase();
    let clean_pattern = pattern.trim_start_matches('*').trim_end_matches('*');

    log::info!("Searching all browser windows for title pattern: {}", clean_pattern);

    unsafe {
        // Get desktop window and iterate through its children (top-level windows)
        let desktop = GetDesktopWindow();
        let first_child = match GetWindow(desktop, GW_CHILD) {
            Ok(h) => h,
            Err(e) => {
                log::warn!("Failed to get first child window: {:?}", e);
                return None;
            }
        };

        if first_child.0.is_null() {
            log::warn!("No windows found under desktop");
            return None;
        }

        let mut hwnd = first_child;
        let mut window_count = 0;

        loop {
            window_count += 1;

            // Check if window is visible
            if IsWindowVisible(hwnd).as_bool() {
                // Get window title
                let mut title_buf: [u16; 512] = [0; 512];
                let len = GetWindowTextW(hwnd, &mut title_buf);

                if len > 0 {
                    let title = String::from_utf16_lossy(&title_buf[..len as usize]);
                    let title_lower = title.to_lowercase();

                    // Check if title matches pattern
                    if title_lower.contains(&clean_pattern) {
                        // Get process name to verify it's a browser
                        if let Some(process_name) = get_process_name_from_hwnd(hwnd) {
                            if is_browser_process(&process_name) {
                                log::info!("Found browser window matching title pattern '{}': {} ({})",
                                    clean_pattern, title, process_name);
                                if let Some(info) = get_extended_window_info_from_hwnd(hwnd) {
                                    return Some(info);
                                }
                            }
                        }
                    }
                }
            }

            // Get next sibling window
            match GetWindow(hwnd, GW_HWNDNEXT) {
                Ok(next) if !next.0.is_null() => hwnd = next,
                _ => break,
            }
        }

        log::info!("Iterated {} windows, no match found for title pattern: {}", window_count, clean_pattern);
    }

    None
}

/// Extract searchable keywords from URL patterns for title-based matching
/// Examples:
/// - "uk.rs-online.com" -> ["rs-online"]
/// - "*.salesforce.com" -> ["salesforce"]
/// - "app.hubspot.com" -> ["hubspot"]
#[cfg(target_os = "windows")]
fn extract_title_keywords_from_url_patterns(url_patterns: &Option<Vec<String>>) -> Vec<String> {
    let mut keywords = Vec::new();

    if let Some(patterns) = url_patterns {
        for pattern in patterns {
            let pattern_lower = pattern.to_lowercase();

            // Remove protocol if present
            let domain = pattern_lower
                .trim_start_matches("https://")
                .trim_start_matches("http://")
                .trim_start_matches("*.");

            // Split by dots to get domain parts
            let parts: Vec<&str> = domain.split('.').collect();

            // Find the main domain part (usually the second-to-last, or the hyphenated one)
            for part in &parts {
                // Skip common TLDs and subdomains
                if part.len() > 2
                    && *part != "com" && *part != "org" && *part != "net"
                    && *part != "co" && *part != "uk" && *part != "www"
                    && *part != "app" && *part != "my" && *part != "portal"
                {
                    // Prioritize hyphenated domain names (like "rs-online")
                    if part.contains('-') || part.len() > 4 {
                        keywords.push(part.to_string());
                    }
                }
            }

            // If no keywords found, try the whole domain minus TLD
            if keywords.is_empty() && parts.len() >= 2 {
                let main_domain = parts.get(parts.len().saturating_sub(2)).unwrap_or(&"");
                if main_domain.len() > 2 {
                    keywords.push(main_domain.to_string());
                }
            }
        }
    }

    // Remove duplicates
    keywords.sort();
    keywords.dedup();

    log::debug!("Extracted title keywords from URL patterns: {:?}", keywords);
    keywords
}

/// Find a browser window by matching its URL origin against patterns
/// This is the most reliable method as it extracts the actual URL from the browser address bar
/// using the uiautomation crate
#[cfg(target_os = "windows")]
fn find_browser_window_by_origin(url_patterns: &[String]) -> Option<ExtendedWindowInfo> {
    use windows::Win32::UI::WindowsAndMessaging::{
        GetDesktopWindow, GetWindow, IsWindowVisible, GetWindowTextW, GW_CHILD, GW_HWNDNEXT,
    };
    use windows::Win32::Foundation::HWND;
    use crate::detection::browser_detection::{
        is_browser_process, get_process_name_from_hwnd, get_extended_window_info_from_hwnd,
    };
    use crate::detection::browser_url::{get_browser_url_uia, url_matches_origin_pattern};

    log::info!("=== ORIGIN-BASED MATCHING START ===");
    log::info!("URL patterns: {:?}", url_patterns);

    let mut browser_count = 0;
    let mut visible_window_count = 0;
    let mut url_extraction_attempts = 0;
    let mut url_extraction_successes = 0;

    unsafe {
        let desktop = GetDesktopWindow();
        let first_child = match GetWindow(desktop, GW_CHILD) {
            Ok(h) => h,
            Err(e) => {
                log::error!("Failed to get first child window: {:?}", e);
                return None;
            }
        };

        if first_child.0.is_null() {
            log::error!("No windows found under desktop");
            return None;
        }

        let mut hwnd = first_child;

        loop {
            if IsWindowVisible(hwnd).as_bool() {
                visible_window_count += 1;

                // Get process name
                if let Some(process_name) = get_process_name_from_hwnd(hwnd) {
                    // Only check browser processes
                    if is_browser_process(&process_name) {
                        browser_count += 1;

                        // Get window title for logging
                        let mut title_buf: [u16; 512] = [0; 512];
                        let len = GetWindowTextW(hwnd, &mut title_buf);
                        let title = if len > 0 {
                            String::from_utf16_lossy(&title_buf[..len as usize])
                        } else {
                            "(no title)".to_string()
                        };

                        log::info!(">>> Browser #{}: {} - hwnd={}", browser_count, process_name, hwnd.0 as isize);
                        log::info!("    Title: '{}'", title);

                        // Try to extract URL using uiautomation crate
                        url_extraction_attempts += 1;
                        if let Some(url) = get_browser_url_uia(hwnd.0 as isize) {
                            url_extraction_successes += 1;
                            log::info!("    URL extracted: {}", url);

                            // Check if URL matches any of the patterns
                            for pattern in url_patterns {
                                if url_matches_origin_pattern(&url, pattern) {
                                    log::info!("=== MATCH FOUND! URL '{}' matches pattern '{}' ===", url, pattern);

                                    // Get full window info
                                    if let Some(info) = get_extended_window_info_from_hwnd(hwnd) {
                                        return Some(info);
                                    }
                                }
                            }
                            log::info!("    URL does not match any patterns");
                        } else {
                            log::warn!("    URL extraction FAILED for this browser window");
                        }
                    }
                }
            }

            // Get next sibling window
            match GetWindow(hwnd, GW_HWNDNEXT) {
                Ok(next) if !next.0.is_null() => hwnd = next,
                _ => break,
            }
        }

        log::info!("=== ORIGIN-BASED MATCHING COMPLETE ===");
        log::info!("Stats: {} visible windows, {} browsers, {} URL attempts, {} URL successes",
            visible_window_count, browser_count, url_extraction_attempts, url_extraction_successes);
    }

    None
}

/// Find a browser window whose title contains any of the domain keywords
/// This is more reliable than URL extraction since browsers show domains in titles
/// Uses GetWindow to iterate through windows (more reliable than EnumWindows callbacks)
#[cfg(target_os = "windows")]
fn find_browser_window_by_domain_keywords(keywords: &[String]) -> Option<ExtendedWindowInfo> {
    use windows::Win32::UI::WindowsAndMessaging::{
        GetDesktopWindow, GetWindow, IsWindowVisible, GetWindowTextW, GW_CHILD, GW_HWNDNEXT,
    };
    use crate::detection::browser_detection::{
        is_browser_process, get_process_name_from_hwnd, get_extended_window_info_from_hwnd,
    };

    log::info!("Searching all browser windows for domain keywords: {:?}", keywords);

    let mut browser_count = 0;
    let mut window_count = 0;

    unsafe {
        // Get desktop window and iterate through its children (top-level windows)
        let desktop = GetDesktopWindow();
        let first_child = match GetWindow(desktop, GW_CHILD) {
            Ok(h) => h,
            Err(e) => {
                log::warn!("Failed to get first child window: {:?}", e);
                return None;
            }
        };

        if first_child.0.is_null() {
            log::warn!("No windows found under desktop");
            return None;
        }

        let mut hwnd = first_child;

        loop {
            window_count += 1;

            // Check if window is visible
            if IsWindowVisible(hwnd).as_bool() {
                // Get window title
                let mut title_buf: [u16; 512] = [0; 512];
                let len = GetWindowTextW(hwnd, &mut title_buf);

                if len > 0 {
                    let title = String::from_utf16_lossy(&title_buf[..len as usize]);

                    // Get process name
                    if let Some(process_name) = get_process_name_from_hwnd(hwnd) {
                        // Only check browser processes
                        if is_browser_process(&process_name) {
                            browser_count += 1;
                            let title_lower = title.to_lowercase();

                            log::info!("Browser window found: '{}' ({})", title, process_name);

                            // Check if title contains any of the domain keywords
                            for keyword in keywords {
                                if title_lower.contains(keyword) {
                                    log::info!("MATCH! Browser '{}' contains keyword '{}'", title, keyword);
                                    if let Some(info) = get_extended_window_info_from_hwnd(hwnd) {
                                        return Some(info);
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Get next sibling window
            match GetWindow(hwnd, GW_HWNDNEXT) {
                Ok(next) if !next.0.is_null() => hwnd = next,
                _ => break,
            }
        }

        log::info!("Iterated {} windows, found {} browser windows, no keyword matches", window_count, browser_count);
    }

    None
}
