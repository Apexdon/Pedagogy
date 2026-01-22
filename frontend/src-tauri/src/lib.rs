//! Pedagogy - AI-powered learning assistant
//!
//! This is the main Tauri library that exposes Rust functionality
//! to the frontend application.

mod commands;
mod detection;
mod overlay;
mod sidepanel;

use commands::detection_commands::{
    capture_screenshot, capture_screenshot_low_res, capture_screenshot_region,
    capture_window, get_active_window_title, get_monitors, is_window_monitoring_active,
    start_window_monitoring, stop_window_monitoring, DetectionState,
    // Smart window detection commands
    get_extended_window_info, smart_match_window, list_browser_windows,
    get_foreground_window_simple,
    // Debug commands
    debug_list_windows,
};
use commands::halo_commands::{
    create_overlay_window, destroy_overlay_window, get_halo_state, hide_halo,
    is_overlay_created, position_overlay_over_window, show_halo, update_halo,
    OverlayState,
};
use commands::sidepanel_commands::{
    create_sidepanel_window, destroy_sidepanel_window, expand_sidepanel,
    minimize_sidepanel, toggle_sidepanel, hide_sidepanel, set_sidepanel_edge,
    set_sidepanel_position, set_sidepanel_auto_minimize, set_sidepanel_target_pattern,
    is_sidepanel_created, get_sidepanel_state, notify_panel_session_started,
    notify_panel_step_changed, notify_panel_session_ended, notify_panel_coordinator_status,
    SidePanelStateWrapper,
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
        // Manage overlay state
        .manage(OverlayState::default())
        // Manage side panel state
        .manage(SidePanelStateWrapper::default())
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
            capture_window,
            get_active_window_title,
            get_monitors,
            start_window_monitoring,
            stop_window_monitoring,
            is_window_monitoring_active,
            // Smart window detection commands
            get_extended_window_info,
            smart_match_window,
            list_browser_windows,
            get_foreground_window_simple,
            debug_list_windows,
            // Halo overlay commands
            create_overlay_window,
            destroy_overlay_window,
            show_halo,
            hide_halo,
            update_halo,
            position_overlay_over_window,
            is_overlay_created,
            get_halo_state,
            // Side panel commands
            create_sidepanel_window,
            destroy_sidepanel_window,
            expand_sidepanel,
            minimize_sidepanel,
            toggle_sidepanel,
            hide_sidepanel,
            set_sidepanel_edge,
            set_sidepanel_position,
            set_sidepanel_auto_minimize,
            set_sidepanel_target_pattern,
            is_sidepanel_created,
            get_sidepanel_state,
            notify_panel_session_started,
            notify_panel_step_changed,
            notify_panel_session_ended,
            notify_panel_coordinator_status,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
