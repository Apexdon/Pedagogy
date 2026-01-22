//! Overlay Window Management
//!
//! Handles creation, positioning, and management of the transparent
//! overlay window that displays halo highlights.

use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tauri::{AppHandle, Emitter, Manager, WebviewUrl, WebviewWindowBuilder};
use tokio::sync::RwLock;

use super::halo::{HaloState, HaloTarget};

/// Overlay window label constant
pub const OVERLAY_WINDOW_LABEL: &str = "halo-overlay";

/// Error type for overlay operations
#[derive(Debug, thiserror::Error)]
pub enum OverlayError {
    #[error("Overlay window not found")]
    WindowNotFound,

    #[error("Failed to create overlay window: {0}")]
    CreateFailed(String),

    #[error("Failed to update overlay: {0}")]
    UpdateFailed(String),

    #[error("Overlay already exists")]
    AlreadyExists,

    #[error("Tauri error: {0}")]
    TauriError(#[from] tauri::Error),
}

/// Event names for overlay communication
pub mod events {
    pub const SHOW_HALO: &str = "halo:show";
    pub const HIDE_HALO: &str = "halo:hide";
    pub const UPDATE_HALO: &str = "halo:update";
    pub const OVERLAY_READY: &str = "halo:ready";
}

/// Payload for halo events
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HaloEventPayload {
    pub target: Option<HaloTarget>,
    pub visible: bool,
    pub window_title: Option<String>,
}

/// Manages the overlay window lifecycle and state
pub struct OverlayManager {
    /// Whether the overlay window is currently created
    is_created: AtomicBool,

    /// Current halo state
    state: Arc<RwLock<HaloState>>,
}

impl Default for OverlayManager {
    fn default() -> Self {
        Self::new()
    }
}

impl OverlayManager {
    /// Create a new overlay manager
    pub fn new() -> Self {
        Self {
            is_created: AtomicBool::new(false),
            state: Arc::new(RwLock::new(HaloState::new())),
        }
    }

    /// Check if the overlay window exists
    pub fn is_created(&self) -> bool {
        self.is_created.load(Ordering::SeqCst)
    }

    /// Get the current halo state
    pub async fn get_state(&self) -> HaloState {
        self.state.read().await.clone()
    }

    /// Create the overlay window
    pub async fn create_overlay(&self, app: &AppHandle) -> Result<(), OverlayError> {
        if self.is_created() {
            log::warn!("Overlay window already exists");
            return Ok(());
        }

        log::info!("Creating overlay window");

        // In development mode, derive the overlay URL from the main window's URL
        // In production, use the bundled overlay.html
        let overlay_url = {
            #[cfg(debug_assertions)]
            {
                // Try to get the main window's URL to derive the dev server origin
                if let Some(main_window) = app.get_webview_window("main") {
                    if let Ok(url) = main_window.url() {
                        let origin = format!("{}://{}", url.scheme(), url.host_str().unwrap_or("localhost"));
                        let port = url.port().map(|p| format!(":{}", p)).unwrap_or_default();
                        let overlay_url_str = format!("{}{}/overlay.html", origin, port);
                        log::info!("Derived overlay URL from main window: {}", overlay_url_str);
                        WebviewUrl::External(overlay_url_str.parse().unwrap())
                    } else {
                        log::warn!("Could not get main window URL, using fallback");
                        WebviewUrl::External("http://localhost:3000/overlay.html".parse().unwrap())
                    }
                } else {
                    log::warn!("Main window not found, using fallback URL");
                    WebviewUrl::External("http://localhost:3000/overlay.html".parse().unwrap())
                }
            }
            #[cfg(not(debug_assertions))]
            {
                WebviewUrl::App("overlay.html".into())
            }
        };

        log::info!("Overlay URL: {:?}", overlay_url);

        // Create the overlay window with transparent background
        let window = WebviewWindowBuilder::new(
            app,
            OVERLAY_WINDOW_LABEL,
            overlay_url,
        )
        .title("")
        .transparent(true)
        .decorations(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .visible(false) // Start hidden
        .resizable(false)
        .focused(false)
        .build()?;

        // Make the window click-through (ignore cursor events)
        #[cfg(target_os = "windows")]
        {
            window.set_ignore_cursor_events(true)?;
        }

        // Get primary monitor size and set window to fullscreen
        if let Some(monitor) = window.primary_monitor()? {
            let size = monitor.size();
            let position = monitor.position();

            window.set_size(tauri::Size::Physical(tauri::PhysicalSize {
                width: size.width,
                height: size.height,
            }))?;

            window.set_position(tauri::Position::Physical(tauri::PhysicalPosition {
                x: position.x,
                y: position.y,
            }))?;
        }

        self.is_created.store(true, Ordering::SeqCst);
        log::info!("Overlay window created successfully");

        Ok(())
    }

    /// Destroy the overlay window
    pub async fn destroy_overlay(&self, app: &AppHandle) -> Result<(), OverlayError> {
        if !self.is_created() {
            return Ok(());
        }

        log::info!("Destroying overlay window");

        if let Some(window) = app.get_webview_window(OVERLAY_WINDOW_LABEL) {
            window.close()?;
        }

        self.is_created.store(false, Ordering::SeqCst);

        // Clear state
        let mut state = self.state.write().await;
        *state = HaloState::new();

        Ok(())
    }

    /// Show the overlay with a halo target
    pub async fn show_halo(
        &self,
        app: &AppHandle,
        target: HaloTarget,
    ) -> Result<(), OverlayError> {
        // Ensure overlay exists
        if !self.is_created() {
            self.create_overlay(app).await?;
        }

        // Update state
        {
            let mut state = self.state.write().await;
            state.set_target(target.clone());
        }

        // Get the overlay window
        let window = app
            .get_webview_window(OVERLAY_WINDOW_LABEL)
            .ok_or(OverlayError::WindowNotFound)?;

        // Make window visible
        window.show()?;

        // Capture values for logging before moving target
        let target_id = target.target_id.clone();
        let step_number = target.step_number;

        // Emit event to frontend
        let payload = HaloEventPayload {
            target: Some(target),
            visible: true,
            window_title: None,
        };

        window.emit(events::SHOW_HALO, payload)?;

        log::info!("Halo shown - target_id: {}, step: {}", target_id, step_number);
        Ok(())
    }

    /// Hide the overlay
    pub async fn hide_halo(&self, app: &AppHandle) -> Result<(), OverlayError> {
        if !self.is_created() {
            return Ok(());
        }

        // Update state
        {
            let mut state = self.state.write().await;
            state.clear_target();
        }

        // Get the overlay window
        if let Some(window) = app.get_webview_window(OVERLAY_WINDOW_LABEL) {
            // Emit hide event
            let payload = HaloEventPayload {
                target: None,
                visible: false,
                window_title: None,
            };
            window.emit(events::HIDE_HALO, payload)?;

            // Wait for fade-out animation to complete (300ms) before hiding window
            // This allows the graceful fade-out animation to play
            let window_clone = window.clone();
            tokio::spawn(async move {
                tokio::time::sleep(std::time::Duration::from_millis(350)).await;
                if let Err(e) = window_clone.hide() {
                    log::warn!("Failed to hide overlay window: {}", e);
                }
            });
        }

        log::debug!("Halo hidden (fade-out animation started)");
        Ok(())
    }

    /// Update the halo position/target
    pub async fn update_halo(
        &self,
        app: &AppHandle,
        target: HaloTarget,
    ) -> Result<(), OverlayError> {
        if !self.is_created() {
            return self.show_halo(app, target).await;
        }

        // Update state
        {
            let mut state = self.state.write().await;
            state.set_target(target.clone());
        }

        // Get the overlay window
        let window = app
            .get_webview_window(OVERLAY_WINDOW_LABEL)
            .ok_or(OverlayError::WindowNotFound)?;

        // Ensure window is visible (it might have been hidden by hide_halo)
        window.show()?;

        // Capture values for logging before moving target
        let target_id = target.target_id.clone();
        let step_number = target.step_number;

        // Emit update event
        let payload = HaloEventPayload {
            target: Some(target),
            visible: true,
            window_title: None,
        };

        window.emit(events::UPDATE_HALO, payload)?;

        log::info!("Halo updated - target_id: {}, step: {}", target_id, step_number);
        Ok(())
    }

    /// Position the overlay over a specific window
    #[cfg(target_os = "windows")]
    pub async fn position_over_window(
        &self,
        app: &AppHandle,
        window_title: &str,
    ) -> Result<(), OverlayError> {
        use windows::Win32::Foundation::{HWND, RECT};
        use windows::Win32::UI::WindowsAndMessaging::{
            FindWindowW, GetWindowRect,
        };

        if !self.is_created() {
            return Err(OverlayError::WindowNotFound);
        }

        let overlay = app
            .get_webview_window(OVERLAY_WINDOW_LABEL)
            .ok_or(OverlayError::WindowNotFound)?;

        // Find the target window and get its rect (all synchronous operations)
        let window_rect: Option<(i32, i32, u32, u32)> = unsafe {
            let title_wide: Vec<u16> = window_title.encode_utf16().chain(std::iter::once(0)).collect();
            let hwnd_result = FindWindowW(None, windows::core::PCWSTR(title_wide.as_ptr()));

            let hwnd = match hwnd_result {
                Ok(h) if h.0 != std::ptr::null_mut() => h,
                _ => {
                    log::warn!("Target window not found: {}", window_title);
                    return Ok(());
                }
            };

            // Get window rect
            let mut rect = RECT::default();
            if GetWindowRect(hwnd, &mut rect).is_ok() {
                let width = (rect.right - rect.left) as u32;
                let height = (rect.bottom - rect.top) as u32;
                Some((rect.left, rect.top, width, height))
            } else {
                None
            }
        };

        // Now handle the async state update and overlay positioning
        if let Some((x, y, width, height)) = window_rect {
            overlay.set_position(tauri::Position::Physical(tauri::PhysicalPosition {
                x,
                y,
            }))?;

            overlay.set_size(tauri::Size::Physical(tauri::PhysicalSize {
                width,
                height,
            }))?;

            // Update state with window info
            let mut state = self.state.write().await;
            state.set_target_window(window_title.to_string(), true);

            log::debug!(
                "Positioned overlay over window: {} ({}x{} at {},{})",
                window_title,
                width,
                height,
                x,
                y
            );
        }

        Ok(())
    }

    #[cfg(not(target_os = "windows"))]
    pub async fn position_over_window(
        &self,
        _app: &AppHandle,
        _window_title: &str,
    ) -> Result<(), OverlayError> {
        // Not implemented for other platforms yet
        Ok(())
    }
}
