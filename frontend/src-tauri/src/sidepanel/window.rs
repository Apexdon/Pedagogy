//! Side Panel Window Management
//!
//! Handles creation, positioning, and state management of the
//! floating guidance panel window positioned at bottom-right corner.

use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tauri::{AppHandle, Emitter, Manager, WebviewUrl, WebviewWindowBuilder};
use tokio::sync::RwLock;

/// Side panel window label constant
pub const PANEL_WINDOW_LABEL: &str = "guidance-panel";

/// Panel dimensions - Floating panel style
const EXPANDED_WIDTH: f64 = 380.0;
const EXPANDED_HEIGHT: f64 = 480.0;
const MINIMIZED_WIDTH: f64 = 56.0;
const MINIMIZED_HEIGHT: f64 = 56.0;
const SCREEN_MARGIN: i32 = 20;  // Margin from screen edges
const TASKBAR_HEIGHT: i32 = 48; // Approximate Windows taskbar height

/// Error type for side panel operations
#[derive(Debug, thiserror::Error)]
pub enum SidePanelError {
    #[error("Side panel window not found")]
    WindowNotFound,

    #[error("Failed to create side panel window: {0}")]
    CreateFailed(String),

    #[error("Failed to update side panel: {0}")]
    UpdateFailed(String),

    #[error("Side panel already exists")]
    AlreadyExists,

    #[error("Tauri error: {0}")]
    TauriError(#[from] tauri::Error),
}

/// Panel state enum
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "lowercase")]
pub enum PanelState {
    #[default]
    Hidden,
    Expanded,
    Minimized,
}

/// Event names for side panel communication
pub mod events {
    pub const SESSION_STARTED: &str = "panel:session_started";
    pub const STEP_CHANGED: &str = "panel:step_changed";
    pub const SESSION_ENDED: &str = "panel:session_ended";
    pub const PANEL_READY: &str = "panel:ready";
    pub const STATE_CHANGED: &str = "panel:state_changed";
    pub const COORDINATOR_STATUS: &str = "panel:coordinator_status";
}

/// Payload for session started event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionStartedPayload {
    pub session_id: String,
    pub query: String,
    pub total_steps: i32,
    pub application_context: Option<String>,
}

/// Payload for step changed event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StepChangedPayload {
    pub step_number: i32,
    pub total_steps: i32,
    pub instruction: String,
    pub detailed_instruction: Option<String>,
    pub action_type: String,
    pub target_label: Option<String>,
    pub confidence: Option<f32>,
}

/// Payload for session ended event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionEndedPayload {
    pub reason: String, // "completed" | "abandoned" | "error"
    pub message: Option<String>,
}

/// Payload for state changed event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StateChangedPayload {
    pub state: PanelState,
    pub previous_state: PanelState,
}

/// Payload for coordinator status event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoordinatorStatusPayload {
    pub status: String,
    pub is_target_active: bool,
    pub target_window: Option<String>,
}

/// Which edge the panel is docked to (kept for API compatibility)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "lowercase")]
pub enum DockedEdge {
    #[default]
    Right,
    Left,
}

/// Internal state of the side panel
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SidePanelState {
    pub state: PanelState,
    pub auto_minimize_enabled: bool,
    pub target_pattern: Option<String>,
}

impl Default for SidePanelState {
    fn default() -> Self {
        Self {
            state: PanelState::Hidden,
            auto_minimize_enabled: true,
            target_pattern: None,
        }
    }
}

/// Manages the side panel window lifecycle and state
pub struct SidePanelManager {
    /// Whether the panel window is currently created
    is_created: AtomicBool,

    /// Current panel state
    state: Arc<RwLock<SidePanelState>>,
}

impl Default for SidePanelManager {
    fn default() -> Self {
        Self::new()
    }
}

impl SidePanelManager {
    /// Create a new side panel manager
    pub fn new() -> Self {
        Self {
            is_created: AtomicBool::new(false),
            state: Arc::new(RwLock::new(SidePanelState::default())),
        }
    }

    /// Check if the panel window exists
    pub fn is_created(&self) -> bool {
        self.is_created.load(Ordering::SeqCst)
    }

    /// Get the current panel state
    pub async fn get_state(&self) -> SidePanelState {
        self.state.read().await.clone()
    }

    /// Create the side panel window
    pub async fn create_panel(&self, app: &AppHandle) -> Result<(), SidePanelError> {
        if self.is_created() {
            log::warn!("Side panel window already exists");
            return Ok(());
        }

        log::info!("Creating side panel window");

        // In development mode, derive the panel URL from the main window's URL
        // In production, use the bundled sidepanel.html
        let panel_url = {
            #[cfg(debug_assertions)]
            {
                if let Some(main_window) = app.get_webview_window("main") {
                    if let Ok(url) = main_window.url() {
                        let origin = format!(
                            "{}://{}",
                            url.scheme(),
                            url.host_str().unwrap_or("localhost")
                        );
                        let port = url.port().map(|p| format!(":{}", p)).unwrap_or_default();
                        let panel_url_str = format!("{}{}/sidepanel.html", origin, port);
                        log::info!("Derived panel URL from main window: {}", panel_url_str);
                        WebviewUrl::External(panel_url_str.parse().unwrap())
                    } else {
                        log::warn!("Could not get main window URL, using fallback");
                        WebviewUrl::External(
                            "http://localhost:3000/sidepanel.html".parse().unwrap(),
                        )
                    }
                } else {
                    log::warn!("Main window not found, using fallback URL");
                    WebviewUrl::External("http://localhost:3000/sidepanel.html".parse().unwrap())
                }
            }
            #[cfg(not(debug_assertions))]
            {
                WebviewUrl::App("sidepanel.html".into())
            }
        };

        log::info!("Panel URL: {:?}", panel_url);

        // Get screen dimensions for positioning at bottom-right
        let (screen_width, screen_height) = self.get_screen_dimensions(app);

        // Position at bottom-right corner with margin
        let x_position = screen_width - EXPANDED_WIDTH as i32 - SCREEN_MARGIN;
        let y_position = screen_height - EXPANDED_HEIGHT as i32 - SCREEN_MARGIN - TASKBAR_HEIGHT;

        // Create the side panel window
        let window = WebviewWindowBuilder::new(app, PANEL_WINDOW_LABEL, panel_url)
            .title("Pedagogy Guidance")
            .inner_size(EXPANDED_WIDTH, EXPANDED_HEIGHT)
            .position(x_position as f64, y_position as f64)
            .resizable(false)
            .always_on_top(true)
            .skip_taskbar(true)
            .decorations(false) // Custom title bar in React
            .transparent(true) // Allow rounded corners
            .visible(false) // Start hidden
            .focused(false) // Don't steal focus on create
            .build()?;

        // Set the window to not take focus when shown
        #[cfg(target_os = "windows")]
        {
            // Note: Unlike overlay, we want the panel to be clickable
            // so we don't set ignore_cursor_events
        }

        self.is_created.store(true, Ordering::SeqCst);

        // Update state
        {
            let mut state = self.state.write().await;
            state.state = PanelState::Hidden;
        }

        log::info!("Side panel window created successfully at ({}, {})", x_position, y_position);

        Ok(())
    }

    /// Destroy the side panel window
    pub async fn destroy_panel(&self, app: &AppHandle) -> Result<(), SidePanelError> {
        if !self.is_created() {
            return Ok(());
        }

        log::info!("Destroying side panel window");

        if let Some(window) = app.get_webview_window(PANEL_WINDOW_LABEL) {
            window.close()?;
        }

        self.is_created.store(false, Ordering::SeqCst);

        // Reset state
        let mut state = self.state.write().await;
        state.state = PanelState::Hidden;

        Ok(())
    }

    /// Show the panel in expanded state
    pub async fn expand(&self, app: &AppHandle) -> Result<(), SidePanelError> {
        if !self.is_created() {
            self.create_panel(app).await?;
        }

        let window = app
            .get_webview_window(PANEL_WINDOW_LABEL)
            .ok_or(SidePanelError::WindowNotFound)?;

        // Resize to expanded dimensions
        window.set_size(tauri::Size::Logical(tauri::LogicalSize {
            width: EXPANDED_WIDTH,
            height: EXPANDED_HEIGHT,
        }))?;

        // Reposition at bottom-right corner for expanded size
        let (screen_width, screen_height) = self.get_screen_dimensions(app);
        let x_position = screen_width - EXPANDED_WIDTH as i32 - SCREEN_MARGIN;
        let y_position = screen_height - EXPANDED_HEIGHT as i32 - SCREEN_MARGIN - TASKBAR_HEIGHT;

        window.set_position(tauri::Position::Physical(tauri::PhysicalPosition {
            x: x_position,
            y: y_position,
        }))?;

        // Show window
        window.show()?;

        // Update state and emit event
        let previous_state = {
            let mut state = self.state.write().await;
            let prev = state.state;
            state.state = PanelState::Expanded;
            prev
        };

        window.emit(
            events::STATE_CHANGED,
            StateChangedPayload {
                state: PanelState::Expanded,
                previous_state,
            },
        )?;

        log::debug!("Side panel expanded");
        Ok(())
    }

    /// Minimize the panel to a small tab
    pub async fn minimize(&self, app: &AppHandle) -> Result<(), SidePanelError> {
        if !self.is_created() {
            return Ok(());
        }

        let window = app
            .get_webview_window(PANEL_WINDOW_LABEL)
            .ok_or(SidePanelError::WindowNotFound)?;

        // Resize to minimized dimensions (small floating icon)
        window.set_size(tauri::Size::Logical(tauri::LogicalSize {
            width: MINIMIZED_WIDTH,
            height: MINIMIZED_HEIGHT,
        }))?;

        // Reposition at bottom-right corner for minimized icon
        let (screen_width, screen_height) = self.get_screen_dimensions(app);
        let x_position = screen_width - MINIMIZED_WIDTH as i32 - SCREEN_MARGIN;
        let y_position = screen_height - MINIMIZED_HEIGHT as i32 - SCREEN_MARGIN - TASKBAR_HEIGHT;

        window.set_position(tauri::Position::Physical(tauri::PhysicalPosition {
            x: x_position,
            y: y_position,
        }))?;

        // Update state and emit event
        let previous_state = {
            let mut state = self.state.write().await;
            let prev = state.state;
            state.state = PanelState::Minimized;
            prev
        };

        window.emit(
            events::STATE_CHANGED,
            StateChangedPayload {
                state: PanelState::Minimized,
                previous_state,
            },
        )?;

        log::debug!("Side panel minimized");
        Ok(())
    }

    /// Toggle between expanded and minimized
    pub async fn toggle(&self, app: &AppHandle) -> Result<(), SidePanelError> {
        let current_state = self.state.read().await.state;
        match current_state {
            PanelState::Expanded => self.minimize(app).await,
            PanelState::Minimized => self.expand(app).await,
            PanelState::Hidden => self.expand(app).await,
        }
    }

    /// Hide the panel completely
    pub async fn hide(&self, app: &AppHandle) -> Result<(), SidePanelError> {
        if !self.is_created() {
            return Ok(());
        }

        if let Some(window) = app.get_webview_window(PANEL_WINDOW_LABEL) {
            window.hide()?;

            let previous_state = {
                let mut state = self.state.write().await;
                let prev = state.state;
                state.state = PanelState::Hidden;
                prev
            };

            window.emit(
                events::STATE_CHANGED,
                StateChangedPayload {
                    state: PanelState::Hidden,
                    previous_state,
                },
            )?;
        }

        log::debug!("Side panel hidden");
        Ok(())
    }

    /// Set the docked edge (kept for API compatibility, no-op for floating panel)
    pub async fn set_docked_edge(
        &self,
        _app: &AppHandle,
        _edge: DockedEdge,
    ) -> Result<(), SidePanelError> {
        // No-op for floating panel - always positioned at bottom-right
        log::debug!("set_docked_edge called but ignored for floating panel");
        Ok(())
    }

    /// Set the vertical position (kept for API compatibility, no-op for floating panel)
    pub async fn set_y_position(
        &self,
        _app: &AppHandle,
        _y: i32,
    ) -> Result<(), SidePanelError> {
        // No-op for floating panel - always positioned at bottom-right
        log::debug!("set_y_position called but ignored for floating panel");
        Ok(())
    }

    /// Set auto-minimize enabled state
    pub async fn set_auto_minimize(&self, enabled: bool) {
        let mut state = self.state.write().await;
        state.auto_minimize_enabled = enabled;
    }

    /// Set the target window pattern for auto-minimize detection
    pub async fn set_target_pattern(&self, pattern: Option<String>) {
        let mut state = self.state.write().await;
        state.target_pattern = pattern;
    }

    /// Check if auto-minimize is enabled
    pub async fn is_auto_minimize_enabled(&self) -> bool {
        self.state.read().await.auto_minimize_enabled
    }

    /// Notify panel of session started
    pub async fn notify_session_started(
        &self,
        app: &AppHandle,
        payload: SessionStartedPayload,
    ) -> Result<(), SidePanelError> {
        if let Some(window) = app.get_webview_window(PANEL_WINDOW_LABEL) {
            window.emit(events::SESSION_STARTED, payload)?;
        }
        Ok(())
    }

    /// Notify panel of step changed
    pub async fn notify_step_changed(
        &self,
        app: &AppHandle,
        payload: StepChangedPayload,
    ) -> Result<(), SidePanelError> {
        if let Some(window) = app.get_webview_window(PANEL_WINDOW_LABEL) {
            window.emit(events::STEP_CHANGED, payload)?;
        }
        Ok(())
    }

    /// Notify panel of session ended
    pub async fn notify_session_ended(
        &self,
        app: &AppHandle,
        payload: SessionEndedPayload,
    ) -> Result<(), SidePanelError> {
        if let Some(window) = app.get_webview_window(PANEL_WINDOW_LABEL) {
            window.emit(events::SESSION_ENDED, payload)?;
        }
        Ok(())
    }

    /// Notify panel of coordinator status
    pub async fn notify_coordinator_status(
        &self,
        app: &AppHandle,
        payload: CoordinatorStatusPayload,
    ) -> Result<(), SidePanelError> {
        if let Some(window) = app.get_webview_window(PANEL_WINDOW_LABEL) {
            window.emit(events::COORDINATOR_STATUS, payload)?;
        }
        Ok(())
    }

    /// Helper to get screen dimensions
    fn get_screen_dimensions(&self, app: &AppHandle) -> (i32, i32) {
        if let Some(main_window) = app.get_webview_window("main") {
            if let Ok(Some(monitor)) = main_window.primary_monitor() {
                let size = monitor.size();
                return (size.width as i32, size.height as i32);
            }
        }
        (1920, 1080)
    }
}
