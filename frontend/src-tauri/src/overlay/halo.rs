//! Halo Target Types and Rendering Logic
//!
//! Defines the data structures for halo targets that will be
//! displayed on the overlay window.

use serde::{Deserialize, Serialize};

/// Bounding box coordinates for a UI element
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BoundingBox {
    pub x1: i32,
    pub y1: i32,
    pub x2: i32,
    pub y2: i32,
}

impl BoundingBox {
    /// Create a new bounding box
    pub fn new(x1: i32, y1: i32, x2: i32, y2: i32) -> Self {
        Self { x1, y1, x2, y2 }
    }

    /// Get the width of the bounding box
    pub fn width(&self) -> i32 {
        self.x2 - self.x1
    }

    /// Get the height of the bounding box
    pub fn height(&self) -> i32 {
        self.y2 - self.y1
    }

    /// Get the center point of the bounding box
    pub fn center(&self) -> (i32, i32) {
        ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)
    }
}

/// Style of the halo highlight
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "lowercase")]
pub enum HaloStyle {
    /// Glowing effect with pulsing animation
    #[default]
    Glow,
    /// Pulsing ring effect
    Pulse,
    /// Dashed outline
    Outline,
    /// Solid border with arrow pointer
    Arrow,
}

/// Represents a target element to be highlighted with a halo
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HaloTarget {
    /// Unique identifier for this halo target
    pub target_id: String,

    /// Bounding box coordinates of the target element
    pub bbox: BoundingBox,

    /// Type of UI element (button, input, dropdown, etc.)
    pub element_type: String,

    /// Label/text of the element (if available)
    pub label: Option<String>,

    /// Current step number in the guidance sequence
    pub step_number: i32,

    /// Type of action to perform (click, type, select, navigate)
    pub action_type: String,

    /// Instruction text to display
    pub instruction: String,

    /// Detailed instruction (optional)
    pub detailed_instruction: Option<String>,

    /// Style of the halo highlight
    #[serde(default)]
    pub halo_style: HaloStyle,

    /// Confidence score of the element match (0.0 - 1.0)
    #[serde(default)]
    pub confidence: f32,
}

impl HaloTarget {
    /// Create a new halo target with required fields
    pub fn new(
        target_id: String,
        bbox: BoundingBox,
        element_type: String,
        step_number: i32,
        action_type: String,
        instruction: String,
    ) -> Self {
        Self {
            target_id,
            bbox,
            element_type,
            label: None,
            step_number,
            action_type,
            instruction,
            detailed_instruction: None,
            halo_style: HaloStyle::default(),
            confidence: 0.0,
        }
    }

    /// Set the label
    pub fn with_label(mut self, label: impl Into<String>) -> Self {
        self.label = Some(label.into());
        self
    }

    /// Set the detailed instruction
    pub fn with_detailed_instruction(mut self, instruction: impl Into<String>) -> Self {
        self.detailed_instruction = Some(instruction.into());
        self
    }

    /// Set the halo style
    pub fn with_style(mut self, style: HaloStyle) -> Self {
        self.halo_style = style;
        self
    }

    /// Set the confidence score
    pub fn with_confidence(mut self, confidence: f32) -> Self {
        self.confidence = confidence.clamp(0.0, 1.0);
        self
    }
}

/// State of the halo overlay
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct HaloState {
    /// Whether the overlay is currently visible
    pub visible: bool,

    /// Current halo target being displayed
    pub current_target: Option<HaloTarget>,

    /// Window title being tracked
    pub target_window_title: Option<String>,

    /// Whether the target window is currently in focus
    pub target_window_active: bool,

    /// Last update timestamp
    pub last_updated: u64,
}

impl HaloState {
    /// Create a new empty halo state
    pub fn new() -> Self {
        Self::default()
    }

    /// Update the current target
    pub fn set_target(&mut self, target: HaloTarget) {
        self.current_target = Some(target);
        self.visible = true;
        self.last_updated = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
    }

    /// Clear the current target
    pub fn clear_target(&mut self) {
        self.current_target = None;
        self.visible = false;
    }

    /// Set the target window info
    pub fn set_target_window(&mut self, title: String, active: bool) {
        self.target_window_title = Some(title);
        self.target_window_active = active;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bounding_box() {
        let bbox = BoundingBox::new(100, 200, 300, 400);
        assert_eq!(bbox.width(), 200);
        assert_eq!(bbox.height(), 200);
        assert_eq!(bbox.center(), (200, 300));
    }

    #[test]
    fn test_halo_target_builder() {
        let target = HaloTarget::new(
            "target-1".to_string(),
            BoundingBox::new(0, 0, 100, 50),
            "button".to_string(),
            1,
            "click".to_string(),
            "Click the Submit button".to_string(),
        )
        .with_label("Submit")
        .with_style(HaloStyle::Glow)
        .with_confidence(0.95);

        assert_eq!(target.label, Some("Submit".to_string()));
        assert_eq!(target.confidence, 0.95);
    }
}
