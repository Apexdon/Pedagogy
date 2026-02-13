//! Side Panel Tauri Commands
//!
//! Provides Tauri commands for controlling the side panel window
//! from the frontend.

use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tauri::{command, AppHandle, State};
use tokio::sync::RwLock;

use crate::sidepanel::{
    DockedEdge, PanelState, SidePanelManager, SidePanelState,
    SessionStartedPayload, StepChangedPayload, SessionEndedPayload, CoordinatorStatusPayload,
    TimingBreakdown,
};

/// Shared state for the side panel manager
pub struct SidePanelStateWrapper(pub Arc<RwLock<SidePanelManager>>);

impl Default for SidePanelStateWrapper {
    fn default() -> Self {
        Self(Arc::new(RwLock::new(SidePanelManager::new())))
    }
}

/// Response for side panel operations
#[derive(Debug, Serialize)]
pub struct SidePanelResponse {
    pub success: bool,
    pub message: String,
}

impl SidePanelResponse {
    pub fn ok(message: impl Into<String>) -> Self {
        Self {
            success: true,
            message: message.into(),
        }
    }

    pub fn error(message: impl Into<String>) -> Self {
        Self {
            success: false,
            message: message.into(),
        }
    }
}

/// Create the side panel window
#[command]
pub async fn create_sidepanel_window(
    app: AppHandle,
    state: State<'_, SidePanelStateWrapper>,
) -> Result<SidePanelResponse, String> {
    let manager = state.0.read().await;

    match manager.create_panel(&app).await {
        Ok(_) => Ok(SidePanelResponse::ok("Side panel window created")),
        Err(e) => {
            log::error!("Failed to create side panel: {}", e);
            Err(e.to_string())
        }
    }
}

/// Destroy the side panel window
#[command]
pub async fn destroy_sidepanel_window(
    app: AppHandle,
    state: State<'_, SidePanelStateWrapper>,
) -> Result<SidePanelResponse, String> {
    let manager = state.0.read().await;

    match manager.destroy_panel(&app).await {
        Ok(_) => Ok(SidePanelResponse::ok("Side panel window destroyed")),
        Err(e) => {
            log::error!("Failed to destroy side panel: {}", e);
            Err(e.to_string())
        }
    }
}

/// Expand the side panel
#[command]
pub async fn expand_sidepanel(
    app: AppHandle,
    state: State<'_, SidePanelStateWrapper>,
) -> Result<SidePanelResponse, String> {
    let manager = state.0.read().await;

    match manager.expand(&app).await {
        Ok(_) => Ok(SidePanelResponse::ok("Side panel expanded")),
        Err(e) => {
            log::error!("Failed to expand side panel: {}", e);
            Err(e.to_string())
        }
    }
}

/// Minimize the side panel
#[command]
pub async fn minimize_sidepanel(
    app: AppHandle,
    state: State<'_, SidePanelStateWrapper>,
) -> Result<SidePanelResponse, String> {
    let manager = state.0.read().await;

    match manager.minimize(&app).await {
        Ok(_) => Ok(SidePanelResponse::ok("Side panel minimized")),
        Err(e) => {
            log::error!("Failed to minimize side panel: {}", e);
            Err(e.to_string())
        }
    }
}

/// Toggle the side panel between expanded and minimized
#[command]
pub async fn toggle_sidepanel(
    app: AppHandle,
    state: State<'_, SidePanelStateWrapper>,
) -> Result<SidePanelResponse, String> {
    let manager = state.0.read().await;

    match manager.toggle(&app).await {
        Ok(_) => Ok(SidePanelResponse::ok("Side panel toggled")),
        Err(e) => {
            log::error!("Failed to toggle side panel: {}", e);
            Err(e.to_string())
        }
    }
}

/// Hide the side panel completely
#[command]
pub async fn hide_sidepanel(
    app: AppHandle,
    state: State<'_, SidePanelStateWrapper>,
) -> Result<SidePanelResponse, String> {
    let manager = state.0.read().await;

    match manager.hide(&app).await {
        Ok(_) => Ok(SidePanelResponse::ok("Side panel hidden")),
        Err(e) => {
            log::error!("Failed to hide side panel: {}", e);
            Err(e.to_string())
        }
    }
}

/// Set the docked edge (left or right)
#[command]
pub async fn set_sidepanel_edge(
    app: AppHandle,
    state: State<'_, SidePanelStateWrapper>,
    edge: String,
) -> Result<SidePanelResponse, String> {
    let manager = state.0.read().await;

    let docked_edge = match edge.to_lowercase().as_str() {
        "left" => DockedEdge::Left,
        "right" => DockedEdge::Right,
        _ => return Err("Invalid edge: must be 'left' or 'right'".to_string()),
    };

    match manager.set_docked_edge(&app, docked_edge).await {
        Ok(_) => Ok(SidePanelResponse::ok(format!("Side panel docked to {}", edge))),
        Err(e) => {
            log::error!("Failed to set docked edge: {}", e);
            Err(e.to_string())
        }
    }
}

/// Set the vertical position
#[command]
pub async fn set_sidepanel_position(
    app: AppHandle,
    state: State<'_, SidePanelStateWrapper>,
    y: i32,
) -> Result<SidePanelResponse, String> {
    let manager = state.0.read().await;

    match manager.set_y_position(&app, y).await {
        Ok(_) => Ok(SidePanelResponse::ok(format!("Side panel position set to y={}", y))),
        Err(e) => {
            log::error!("Failed to set position: {}", e);
            Err(e.to_string())
        }
    }
}

/// Set auto-minimize enabled/disabled
#[command]
pub async fn set_sidepanel_auto_minimize(
    state: State<'_, SidePanelStateWrapper>,
    enabled: bool,
) -> Result<SidePanelResponse, String> {
    let manager = state.0.read().await;
    manager.set_auto_minimize(enabled).await;
    Ok(SidePanelResponse::ok(format!(
        "Auto-minimize {}",
        if enabled { "enabled" } else { "disabled" }
    )))
}

/// Set the target window pattern for auto-minimize
#[command]
pub async fn set_sidepanel_target_pattern(
    state: State<'_, SidePanelStateWrapper>,
    pattern: Option<String>,
) -> Result<SidePanelResponse, String> {
    let manager = state.0.read().await;
    manager.set_target_pattern(pattern.clone()).await;
    Ok(SidePanelResponse::ok(format!(
        "Target pattern set to {:?}",
        pattern
    )))
}

/// Check if the side panel window is created
#[command]
pub async fn is_sidepanel_created(
    state: State<'_, SidePanelStateWrapper>,
) -> Result<bool, String> {
    let manager = state.0.read().await;
    Ok(manager.is_created())
}

/// Get the current side panel state
#[command]
pub async fn get_sidepanel_state(
    state: State<'_, SidePanelStateWrapper>,
) -> Result<SidePanelState, String> {
    let manager = state.0.read().await;
    Ok(manager.get_state().await)
}

/// Notify panel of session started
#[command(rename_all = "snake_case")]
pub async fn notify_panel_session_started(
    app: AppHandle,
    state: State<'_, SidePanelStateWrapper>,
    session_id: String,
    query: String,
    total_steps: i32,
    application_context: Option<String>,
) -> Result<SidePanelResponse, String> {
    let manager = state.0.read().await;

    let payload = SessionStartedPayload {
        session_id,
        query,
        total_steps,
        application_context,
    };

    match manager.notify_session_started(&app, payload).await {
        Ok(_) => Ok(SidePanelResponse::ok("Session started notification sent")),
        Err(e) => {
            log::error!("Failed to notify session started: {}", e);
            Err(e.to_string())
        }
    }
}

/// Notify panel of step changed
#[command(rename_all = "snake_case")]
pub async fn notify_panel_step_changed(
    app: AppHandle,
    state: State<'_, SidePanelStateWrapper>,
    step_number: i32,
    total_steps: i32,
    instruction: String,
    detailed_instruction: Option<String>,
    action_type: String,
    target_label: Option<String>,
    confidence: Option<f32>,
    timing: Option<TimingBreakdown>,
) -> Result<SidePanelResponse, String> {
    let manager = state.0.read().await;

    let payload = StepChangedPayload {
        step_number,
        total_steps,
        instruction,
        detailed_instruction,
        action_type,
        target_label,
        confidence,
        timing,
    };

    match manager.notify_step_changed(&app, payload).await {
        Ok(_) => Ok(SidePanelResponse::ok("Step changed notification sent")),
        Err(e) => {
            log::error!("Failed to notify step changed: {}", e);
            Err(e.to_string())
        }
    }
}

/// Notify panel of session ended
#[command]
pub async fn notify_panel_session_ended(
    app: AppHandle,
    state: State<'_, SidePanelStateWrapper>,
    reason: String,
    message: Option<String>,
) -> Result<SidePanelResponse, String> {
    let manager = state.0.read().await;

    let payload = SessionEndedPayload { reason, message };

    match manager.notify_session_ended(&app, payload).await {
        Ok(_) => Ok(SidePanelResponse::ok("Session ended notification sent")),
        Err(e) => {
            log::error!("Failed to notify session ended: {}", e);
            Err(e.to_string())
        }
    }
}

/// Notify panel of coordinator status change
#[command(rename_all = "snake_case")]
pub async fn notify_panel_coordinator_status(
    app: AppHandle,
    state: State<'_, SidePanelStateWrapper>,
    status: String,
    is_target_active: bool,
    target_window: Option<String>,
) -> Result<SidePanelResponse, String> {
    let manager = state.0.read().await;

    let payload = CoordinatorStatusPayload {
        status,
        is_target_active,
        target_window,
    };

    match manager.notify_coordinator_status(&app, payload).await {
        Ok(_) => Ok(SidePanelResponse::ok("Coordinator status notification sent")),
        Err(e) => {
            log::error!("Failed to notify coordinator status: {}", e);
            Err(e.to_string())
        }
    }
}
