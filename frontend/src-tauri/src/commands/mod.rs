//! Tauri command modules.
//!
//! Exposes Rust functionality to the frontend via Tauri's invoke system.

pub mod detection_commands;
pub mod halo_commands;
pub mod sidepanel_commands;

// Re-export all commands and types for easy access
pub use detection_commands::*;
pub use halo_commands::*;
pub use sidepanel_commands::*;
