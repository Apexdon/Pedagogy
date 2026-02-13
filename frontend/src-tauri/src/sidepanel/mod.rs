//! Side Panel Module
//!
//! Manages the docked guidance panel window with auto-minimize behavior.
//! The panel shows step-by-step guidance and automatically minimizes
//! when the target application gains focus.

pub mod window;

pub use window::{
    SidePanelManager, SidePanelError, PanelState, SidePanelState,
    DockedEdge, PANEL_WINDOW_LABEL,
    SessionStartedPayload, StepChangedPayload, SessionEndedPayload, CoordinatorStatusPayload,
    TimingBreakdown,
};
