//! Screen capture functionality using xcap crate.
//!
//! Provides full-resolution and low-resolution capture options
//! with Base64 PNG encoding for API transmission.
//! Also supports capturing specific windows by title pattern.

use base64::{Engine as _, engine::general_purpose::STANDARD as BASE64};
use image::{DynamicImage, ImageFormat};
use std::io::Cursor;
use xcap::{Monitor, Window};

/// Error type for screenshot operations
#[derive(Debug, thiserror::Error)]
pub enum ScreenshotError {
    #[error("Failed to enumerate monitors: {0}")]
    MonitorEnumeration(String),

    #[error("No monitors found")]
    NoMonitors,

    #[error("Capture failed: {0}")]
    CaptureFailed(String),

    #[error("Image encoding failed: {0}")]
    EncodingFailed(String),
}

/// Result of a screen capture operation
#[derive(Debug, Clone, serde::Serialize)]
pub struct CaptureResult {
    /// Base64 encoded PNG image
    pub image_base64: String,
    /// Original image width
    pub width: u32,
    /// Original image height
    pub height: u32,
    /// Monitor name/identifier
    pub monitor_name: String,
}

/// Captures the primary monitor screen as Base64 PNG.
///
/// Returns full resolution screenshot suitable for CV analysis.
pub fn capture_primary() -> Result<CaptureResult, ScreenshotError> {
    let monitors = Monitor::all()
        .map_err(|e| ScreenshotError::MonitorEnumeration(e.to_string()))?;

    // Find primary monitor or use first available
    let primary = monitors
        .into_iter()
        .find(|m| m.is_primary())
        .or_else(|| Monitor::all().ok()?.into_iter().next())
        .ok_or(ScreenshotError::NoMonitors)?;

    let monitor_name = primary.name().to_string();

    // Capture the screen
    let image = primary.capture_image()
        .map_err(|e| ScreenshotError::CaptureFailed(e.to_string()))?;

    let width = image.width();
    let height = image.height();

    // Convert to PNG bytes
    let dynamic_image = DynamicImage::ImageRgba8(image);
    let mut buffer = Cursor::new(Vec::new());
    dynamic_image.write_to(&mut buffer, ImageFormat::Png)
        .map_err(|e| ScreenshotError::EncodingFailed(e.to_string()))?;

    // Encode to Base64
    let image_base64 = BASE64.encode(buffer.into_inner());

    Ok(CaptureResult {
        image_base64,
        width,
        height,
        monitor_name,
    })
}

/// Captures screen at reduced resolution for faster processing.
///
/// Useful for quick detection or low-bandwidth scenarios.
/// Default target: 854x480 (480p equivalent)
pub fn capture_low_res(max_width: u32, max_height: u32) -> Result<CaptureResult, ScreenshotError> {
    let full_capture = capture_primary()?;

    // Decode the full-resolution image
    let image_bytes = BASE64.decode(&full_capture.image_base64)
        .map_err(|e| ScreenshotError::EncodingFailed(e.to_string()))?;

    let img = image::load_from_memory(&image_bytes)
        .map_err(|e| ScreenshotError::EncodingFailed(e.to_string()))?;

    // Calculate resize dimensions maintaining aspect ratio
    let (orig_w, orig_h) = (img.width(), img.height());
    let scale = (max_width as f32 / orig_w as f32)
        .min(max_height as f32 / orig_h as f32)
        .min(1.0); // Don't upscale

    let new_width = (orig_w as f32 * scale) as u32;
    let new_height = (orig_h as f32 * scale) as u32;

    // Resize image
    let resized = img.resize(new_width, new_height, image::imageops::FilterType::Triangle);

    // Encode back to PNG
    let mut buffer = Cursor::new(Vec::new());
    resized.write_to(&mut buffer, ImageFormat::Png)
        .map_err(|e| ScreenshotError::EncodingFailed(e.to_string()))?;

    Ok(CaptureResult {
        image_base64: BASE64.encode(buffer.into_inner()),
        width: new_width,
        height: new_height,
        monitor_name: full_capture.monitor_name,
    })
}

/// Captures a specific window by title pattern.
///
/// Uses case-insensitive contains matching.
/// Returns the first matching window found.
pub fn capture_window_by_title(title_pattern: &str) -> Result<CaptureResult, ScreenshotError> {
    let windows = Window::all()
        .map_err(|e| ScreenshotError::CaptureFailed(format!("Failed to enumerate windows: {}", e)))?;

    // Find window matching the pattern (case-insensitive contains)
    let pattern_lower = title_pattern.to_lowercase();
    let target_window = windows
        .into_iter()
        .find(|w| w.title().to_lowercase().contains(&pattern_lower))
        .ok_or_else(|| ScreenshotError::CaptureFailed(format!("No window matching '{}' found", title_pattern)))?;

    let window_name = target_window.title().to_string();

    // Capture the window
    let image = target_window.capture_image()
        .map_err(|e| ScreenshotError::CaptureFailed(format!("Failed to capture window '{}': {}", window_name, e)))?;

    let width = image.width();
    let height = image.height();

    // Convert to PNG bytes
    let dynamic_image = DynamicImage::ImageRgba8(image);
    let mut buffer = Cursor::new(Vec::new());
    dynamic_image.write_to(&mut buffer, ImageFormat::Png)
        .map_err(|e| ScreenshotError::EncodingFailed(e.to_string()))?;

    // Encode to Base64
    let image_base64 = BASE64.encode(buffer.into_inner());

    Ok(CaptureResult {
        image_base64,
        width,
        height,
        monitor_name: window_name, // Use window title instead of monitor name
    })
}

/// Captures a specific window by its HWND (window handle).
///
/// This is more reliable than title matching when the HWND is known,
/// as it doesn't require string pattern matching.
pub fn capture_window_by_hwnd(hwnd: isize) -> Result<CaptureResult, ScreenshotError> {
    let windows = Window::all()
        .map_err(|e| ScreenshotError::CaptureFailed(format!("Failed to enumerate windows: {}", e)))?;

    // Find window matching the HWND
    let target_window = windows
        .into_iter()
        .find(|w| w.id() as isize == hwnd)
        .ok_or_else(|| ScreenshotError::CaptureFailed(format!("No window with HWND {} found", hwnd)))?;

    let window_name = target_window.title().to_string();

    // Capture the window
    let image = target_window.capture_image()
        .map_err(|e| ScreenshotError::CaptureFailed(format!("Failed to capture window '{}': {}", window_name, e)))?;

    let width = image.width();
    let height = image.height();

    // Convert to PNG bytes
    let dynamic_image = DynamicImage::ImageRgba8(image);
    let mut buffer = Cursor::new(Vec::new());
    dynamic_image.write_to(&mut buffer, ImageFormat::Png)
        .map_err(|e| ScreenshotError::EncodingFailed(e.to_string()))?;

    // Encode to Base64
    let image_base64 = BASE64.encode(buffer.into_inner());

    Ok(CaptureResult {
        image_base64,
        width,
        height,
        monitor_name: window_name, // Use window title instead of monitor name
    })
}

/// Captures a specific region of the screen.
///
/// Coordinates are in screen pixels.
pub fn capture_region(x: i32, y: i32, width: u32, height: u32) -> Result<CaptureResult, ScreenshotError> {
    let full_capture = capture_primary()?;

    // Decode the full-resolution image
    let image_bytes = BASE64.decode(&full_capture.image_base64)
        .map_err(|e| ScreenshotError::EncodingFailed(e.to_string()))?;

    let img = image::load_from_memory(&image_bytes)
        .map_err(|e| ScreenshotError::EncodingFailed(e.to_string()))?;

    // Crop the image
    let cropped = img.crop_imm(
        x.max(0) as u32,
        y.max(0) as u32,
        width.min(img.width()),
        height.min(img.height()),
    );

    // Encode to PNG
    let mut buffer = Cursor::new(Vec::new());
    cropped.write_to(&mut buffer, ImageFormat::Png)
        .map_err(|e| ScreenshotError::EncodingFailed(e.to_string()))?;

    Ok(CaptureResult {
        image_base64: BASE64.encode(buffer.into_inner()),
        width: cropped.width(),
        height: cropped.height(),
        monitor_name: full_capture.monitor_name,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_capture_primary() {
        // This test requires a display, skip in headless CI
        if std::env::var("CI").is_ok() {
            return;
        }

        let result = capture_primary();
        assert!(result.is_ok(), "Capture should succeed: {:?}", result.err());

        let capture = result.unwrap();
        assert!(!capture.image_base64.is_empty(), "Image should not be empty");
        assert!(capture.width > 0, "Width should be positive");
        assert!(capture.height > 0, "Height should be positive");
    }

    #[test]
    fn test_capture_low_res() {
        if std::env::var("CI").is_ok() {
            return;
        }

        let result = capture_low_res(854, 480);
        assert!(result.is_ok());

        let capture = result.unwrap();
        assert!(capture.width <= 854);
        assert!(capture.height <= 480);
    }
}
