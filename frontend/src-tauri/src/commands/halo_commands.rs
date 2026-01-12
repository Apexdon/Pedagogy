//! Halo Overlay Tauri Commands
//!
//! Provides Tauri commands for controlling the halo overlay
//! from the frontend.

use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tauri::{command, AppHandle, State};
use tokio::sync::RwLock;

use crate::overlay::{BoundingBox, HaloStyle, HaloTarget, OverlayManager};

/// Shared state for the overlay manager
pub struct OverlayState(pub Arc<RwLock<OverlayManager>>);

impl Default for OverlayState {
    fn default() -> Self {
        Self(Arc::new(RwLock::new(OverlayManager::new())))
    }
}

/// Response for overlay operations
#[derive(Debug, Serialize)]
pub struct OverlayResponse {
    pub success: bool,
    pub message: String,
}

impl OverlayResponse {
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

/// Request to show a halo target
#[derive(Debug, Deserialize)]
pub struct ShowHaloRequest {
    pub target_id: String,
    pub bbox: BoundingBoxInput,
    pub element_type: String,
    pub label: Option<String>,
    pub step_number: i32,
    pub action_type: String,
    pub instruction: String,
    pub detailed_instruction: Option<String>,
    #[serde(default)]
    pub halo_style: String,
    #[serde(default)]
    pub confidence: f32,
}

#[derive(Debug, Deserialize)]
pub struct BoundingBoxInput {
    pub x1: i32,
    pub y1: i32,
    pub x2: i32,
    pub y2: i32,
}

impl From<BoundingBoxInput> for BoundingBox {
    fn from(input: BoundingBoxInput) -> Self {
        BoundingBox::new(input.x1, input.y1, input.x2, input.y2)
    }
}

impl From<ShowHaloRequest> for HaloTarget {
    fn from(req: ShowHaloRequest) -> Self {
        let style = match req.halo_style.to_lowercase().as_str() {
            "pulse" => HaloStyle::Pulse,
            "outline" => HaloStyle::Outline,
            "arrow" => HaloStyle::Arrow,
            _ => HaloStyle::Glow,
        };

        HaloTarget {
            target_id: req.target_id,
            bbox: req.bbox.into(),
            element_type: req.element_type,
            label: req.label,
            step_number: req.step_number,
            action_type: req.action_type,
            instruction: req.instruction,
            detailed_instruction: req.detailed_instruction,
            halo_style: style,
            confidence: req.confidence,
        }
    }
}

/// Create the overlay window
#[command]
pub async fn create_overlay_window(
    app: AppHandle,
    state: State<'_, OverlayState>,
) -> Result<OverlayResponse, String> {
    let manager = state.0.read().await;

    match manager.create_overlay(&app).await {
        Ok(_) => Ok(OverlayResponse::ok("Overlay window created")),
        Err(e) => {
            log::error!("Failed to create overlay: {}", e);
            Err(e.to_string())
        }
    }
}

/// Destroy the overlay window
#[command]
pub async fn destroy_overlay_window(
    app: AppHandle,
    state: State<'_, OverlayState>,
) -> Result<OverlayResponse, String> {
    let manager = state.0.read().await;

    match manager.destroy_overlay(&app).await {
        Ok(_) => Ok(OverlayResponse::ok("Overlay window destroyed")),
        Err(e) => {
            log::error!("Failed to destroy overlay: {}", e);
            Err(e.to_string())
        }
    }
}

/// Show the halo on a target element
#[command]
pub async fn show_halo(
    app: AppHandle,
    state: State<'_, OverlayState>,
    request: ShowHaloRequest,
) -> Result<OverlayResponse, String> {
    let manager = state.0.read().await;
    let target: HaloTarget = request.into();

    match manager.show_halo(&app, target).await {
        Ok(_) => Ok(OverlayResponse::ok("Halo shown")),
        Err(e) => {
            log::error!("Failed to show halo: {}", e);
            Err(e.to_string())
        }
    }
}

/// Hide the halo
#[command]
pub async fn hide_halo(
    app: AppHandle,
    state: State<'_, OverlayState>,
) -> Result<OverlayResponse, String> {
    let manager = state.0.read().await;

    match manager.hide_halo(&app).await {
        Ok(_) => Ok(OverlayResponse::ok("Halo hidden")),
        Err(e) => {
            log::error!("Failed to hide halo: {}", e);
            Err(e.to_string())
        }
    }
}

/// Update the halo position/target
#[command]
pub async fn update_halo(
    app: AppHandle,
    state: State<'_, OverlayState>,
    request: ShowHaloRequest,
) -> Result<OverlayResponse, String> {
    let manager = state.0.read().await;
    let target: HaloTarget = request.into();

    match manager.update_halo(&app, target).await {
        Ok(_) => Ok(OverlayResponse::ok("Halo updated")),
        Err(e) => {
            log::error!("Failed to update halo: {}", e);
            Err(e.to_string())
        }
    }
}

/// Position the overlay over a specific window
#[command]
pub async fn position_overlay_over_window(
    app: AppHandle,
    state: State<'_, OverlayState>,
    window_title: String,
) -> Result<OverlayResponse, String> {
    let manager = state.0.read().await;

    match manager.position_over_window(&app, &window_title).await {
        Ok(_) => Ok(OverlayResponse::ok(format!(
            "Overlay positioned over: {}",
            window_title
        ))),
        Err(e) => {
            log::error!("Failed to position overlay: {}", e);
            Err(e.to_string())
        }
    }
}

/// Check if the overlay window is created
#[command]
pub async fn is_overlay_created(state: State<'_, OverlayState>) -> Result<bool, String> {
    let manager = state.0.read().await;
    Ok(manager.is_created())
}

/// Get the current halo state
#[command]
pub async fn get_halo_state(
    state: State<'_, OverlayState>,
) -> Result<crate::overlay::halo::HaloState, String> {
    let manager = state.0.read().await;
    Ok(manager.get_state().await)
}
