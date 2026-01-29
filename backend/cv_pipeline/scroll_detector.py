"""
Scroll Offset Detector

Detects vertical scroll offset between two screenshots using template matching.
This is much faster than OCR-based position detection (~10-50ms vs ~500-2000ms)
and provides pixel-perfect accuracy.

Used for updating halo position when user scrolls without re-running full CV.
"""

import time
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass
class ScrollDetectionResult:
    """Result of scroll offset detection."""
    success: bool
    scroll_offset_y: int  # Positive = scrolled down, Negative = scrolled up
    scroll_offset_x: int  # For horizontal scroll (usually 0)
    confidence: float  # Match confidence (0-1)
    processing_time_ms: float
    message: str


class ScrollOffsetDetector:
    """
    Detects scroll offset between reference and current screenshots.

    Uses OpenCV template matching to find where a strip from the reference
    image appears in the current image, then calculates the offset.
    """

    def __init__(
        self,
        strip_height: int = 150,
        strip_y_ratio: float = 0.35,
        min_confidence: float = 0.65,
        search_margin: int = 500,
    ):
        """
        Initialize the scroll detector.

        Args:
            strip_height: Height of the template strip to match (pixels)
            strip_y_ratio: Y position of strip as ratio of image height (0-1)
            min_confidence: Minimum match confidence to consider valid
            search_margin: Vertical search range above/below original position
        """
        self.strip_height = strip_height
        self.strip_y_ratio = strip_y_ratio
        self.min_confidence = min_confidence
        self.search_margin = search_margin

    def detect_scroll_offset(
        self,
        reference_image: np.ndarray,
        current_image: np.ndarray,
    ) -> ScrollDetectionResult:
        """
        Detect vertical scroll offset between reference and current images.

        Args:
            reference_image: The original screenshot (BGR numpy array)
            current_image: The current screenshot (BGR numpy array)

        Returns:
            ScrollDetectionResult with offset and confidence
        """
        start_time = time.perf_counter()

        # Validate input images
        if reference_image is None or current_image is None:
            return ScrollDetectionResult(
                success=False,
                scroll_offset_y=0,
                scroll_offset_x=0,
                confidence=0.0,
                processing_time_ms=0.0,
                message="Invalid input images"
            )

        # Get image dimensions
        ref_h, ref_w = reference_image.shape[:2]
        cur_h, cur_w = current_image.shape[:2]

        # Images should be same size (or close)
        if abs(ref_w - cur_w) > 10 or abs(ref_h - cur_h) > 10:
            return ScrollDetectionResult(
                success=False,
                scroll_offset_y=0,
                scroll_offset_x=0,
                confidence=0.0,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
                message=f"Image size mismatch: ref={ref_w}x{ref_h}, cur={cur_w}x{cur_h}"
            )

        # Convert to grayscale for faster matching
        if len(reference_image.shape) == 3:
            ref_gray = cv2.cvtColor(reference_image, cv2.COLOR_BGR2GRAY)
        else:
            ref_gray = reference_image

        if len(current_image.shape) == 3:
            cur_gray = cv2.cvtColor(current_image, cv2.COLOR_BGR2GRAY)
        else:
            cur_gray = current_image

        # Extract template strip from reference image
        # Use a strip from the middle area (avoids headers/footers that may be fixed)
        strip_y = int(ref_h * self.strip_y_ratio)
        strip_y = max(0, min(strip_y, ref_h - self.strip_height))

        # Use center portion horizontally to avoid scrollbars
        margin_x = int(ref_w * 0.1)  # 10% margin on each side
        strip_x1 = margin_x
        strip_x2 = ref_w - margin_x

        template = ref_gray[strip_y:strip_y + self.strip_height, strip_x1:strip_x2]

        if template.size == 0:
            return ScrollDetectionResult(
                success=False,
                scroll_offset_y=0,
                scroll_offset_x=0,
                confidence=0.0,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
                message="Failed to extract template strip"
            )

        # Define search region in current image
        # Search above and below the original position
        search_y1 = max(0, strip_y - self.search_margin)
        search_y2 = min(cur_h, strip_y + self.strip_height + self.search_margin)

        search_region = cur_gray[search_y1:search_y2, strip_x1:strip_x2]

        if search_region.shape[0] < template.shape[0] or search_region.shape[1] < template.shape[1]:
            return ScrollDetectionResult(
                success=False,
                scroll_offset_y=0,
                scroll_offset_x=0,
                confidence=0.0,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
                message="Search region smaller than template"
            )

        # Perform template matching
        result = cv2.matchTemplate(search_region, template, cv2.TM_CCOEFF_NORMED)

        # Find best match location
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        processing_time = (time.perf_counter() - start_time) * 1000

        # Check if match is good enough
        if max_val < self.min_confidence:
            return ScrollDetectionResult(
                success=False,
                scroll_offset_y=0,
                scroll_offset_x=0,
                confidence=max_val,
                processing_time_ms=processing_time,
                message=f"Low confidence match ({max_val:.2f} < {self.min_confidence}). Content may have changed."
            )

        # Calculate scroll offset
        # max_loc is relative to search_region, convert to image coordinates
        found_y = search_y1 + max_loc[1]
        scroll_offset_y = strip_y - found_y  # Positive = scrolled down

        # For horizontal scroll (usually not needed, but included for completeness)
        scroll_offset_x = 0  # We're not detecting horizontal scroll currently

        return ScrollDetectionResult(
            success=True,
            scroll_offset_y=scroll_offset_y,
            scroll_offset_x=scroll_offset_x,
            confidence=max_val,
            processing_time_ms=processing_time,
            message=f"Detected scroll offset: {scroll_offset_y}px (confidence: {max_val:.2f})"
        )

    def detect_with_multiple_strips(
        self,
        reference_image: np.ndarray,
        current_image: np.ndarray,
        num_strips: int = 3,
    ) -> ScrollDetectionResult:
        """
        More robust scroll detection using multiple strips.

        Uses strips at different Y positions and takes the median offset.
        More resilient to partial content changes.

        Args:
            reference_image: The original screenshot
            current_image: The current screenshot
            num_strips: Number of strips to use (odd number recommended)

        Returns:
            ScrollDetectionResult with median offset
        """
        start_time = time.perf_counter()

        # Define strip positions (avoid top 20% and bottom 20%)
        strip_ratios = [0.25 + (i * 0.5 / (num_strips - 1)) for i in range(num_strips)] if num_strips > 1 else [0.4]

        offsets = []
        confidences = []

        for ratio in strip_ratios:
            # Create detector with this strip position
            detector = ScrollOffsetDetector(
                strip_height=self.strip_height,
                strip_y_ratio=ratio,
                min_confidence=self.min_confidence,
                search_margin=self.search_margin,
            )

            result = detector.detect_scroll_offset(reference_image, current_image)

            if result.success:
                offsets.append(result.scroll_offset_y)
                confidences.append(result.confidence)

        processing_time = (time.perf_counter() - start_time) * 1000

        if not offsets:
            return ScrollDetectionResult(
                success=False,
                scroll_offset_y=0,
                scroll_offset_x=0,
                confidence=0.0,
                processing_time_ms=processing_time,
                message="No strips matched - content likely changed significantly"
            )

        # Use median offset for robustness
        median_offset = int(np.median(offsets))
        avg_confidence = np.mean(confidences)

        return ScrollDetectionResult(
            success=True,
            scroll_offset_y=median_offset,
            scroll_offset_x=0,
            confidence=avg_confidence,
            processing_time_ms=processing_time,
            message=f"Detected scroll offset: {median_offset}px (from {len(offsets)}/{num_strips} strips)"
        )


def apply_scroll_offset_to_bbox(
    bbox: dict,
    scroll_offset_y: int,
    scroll_offset_x: int = 0,
    image_height: int = 0,
    image_width: int = 0,
) -> Tuple[Optional[dict], bool]:
    """
    Apply scroll offset to a bounding box.

    Args:
        bbox: Original bounding box {x1, y1, x2, y2}
        scroll_offset_y: Vertical scroll offset (positive = scrolled down)
        scroll_offset_x: Horizontal scroll offset
        image_height: Image height for bounds checking
        image_width: Image width for bounds checking

    Returns:
        Tuple of (new_bbox, is_visible)
        new_bbox is None if element scrolled completely off-screen
    """
    new_bbox = {
        'x1': bbox['x1'] - scroll_offset_x,
        'y1': bbox['y1'] - scroll_offset_y,
        'x2': bbox['x2'] - scroll_offset_x,
        'y2': bbox['y2'] - scroll_offset_y,
    }

    # Check if element is still visible
    if image_height > 0:
        # Element is off-screen if completely above or below viewport
        if new_bbox['y2'] < 0 or new_bbox['y1'] > image_height:
            return None, False

    if image_width > 0:
        if new_bbox['x2'] < 0 or new_bbox['x1'] > image_width:
            return None, False

    # Clamp to visible area
    if image_height > 0:
        new_bbox['y1'] = max(0, new_bbox['y1'])
        new_bbox['y2'] = min(image_height, new_bbox['y2'])

    if image_width > 0:
        new_bbox['x1'] = max(0, new_bbox['x1'])
        new_bbox['x2'] = min(image_width, new_bbox['x2'])

    return new_bbox, True


# Global detector instance (lazy loaded)
_scroll_detector: Optional[ScrollOffsetDetector] = None


def get_scroll_detector() -> ScrollOffsetDetector:
    """Get or create the global scroll detector instance."""
    global _scroll_detector

    if _scroll_detector is None:
        _scroll_detector = ScrollOffsetDetector(
            strip_height=150,
            strip_y_ratio=0.35,
            min_confidence=0.65,
            search_margin=500,
        )

    return _scroll_detector
