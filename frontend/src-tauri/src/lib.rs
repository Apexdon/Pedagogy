//! Pedagogy - AI-powered learning assistant
//!
//! This is the main Tauri library that exposes Rust functionality
//! to the frontend application.

mod commands;
mod detection;

use commands::detection_commands::{
    capture_screenshot, capture_screenshot_low_res, capture_screenshot_region,
    get_active_window_title, get_monitors, is_window_monitoring_active,
    start_window_monitoring, stop_window_monitoring, DetectionState,
};
use tauri::Manager;

/// Simple greet command for testing
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! Welcome to Pedagogy.", name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        // Manage detection state
        .manage(DetectionState::default())
        .setup(|app| {
            // Setup logging in debug mode
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // Get the main window
            let _window = app.get_webview_window("main").unwrap();

            log::info!("Pedagogy application started");
            log::info!("Screen capture and detection modules initialized");

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            // Existing commands
            greet,
            // Detection commands
            capture_screenshot,
            capture_screenshot_low_res,
            capture_screenshot_region,
            get_active_window_title,
            get_monitors,
            start_window_monitoring,
            stop_window_monitoring,
            is_window_monitoring_active,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
