//! Tauri commands for detection functionality.
//!
//! These commands are exposed to the frontend via invoke().

use crate::detection::{
    screenshot, window_monitor, CaptureResult, WindowInfo, WindowPattern,
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
