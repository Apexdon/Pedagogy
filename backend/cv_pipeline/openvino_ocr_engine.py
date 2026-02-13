"""
OpenVINO-Accelerated OCR Engine

Uses RapidOCR with OpenVINO backend for fast text extraction.
RapidOCR uses PaddleOCR models pre-converted to ONNX/OpenVINO format.

Performance: ~100-300ms (vs ~38s for native PaddleOCR)

OPTIMIZATION: Two-stage recognition with box filtering
- Stage 1: Run text detection to find all text boxes (~500ms)
- Stage 2: Filter to top N boxes by area (skip small text)
- Stage 3: Run batch recognition only on filtered boxes
- Result: ~2x faster for typical UI screenshots

OPTIMIZATION: Thread configuration
- Explicit thread count (~20% faster than auto-detect)
- Set via OCR_INFERENCE_THREADS env var or constructor parameter
"""

import os
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

from .data_classes import BoundingBox, TextRegion, OCRResult, RecognitionRegionTiming


# Default max regions to recognize (set to 0 to disable filtering)
DEFAULT_MAX_REGIONS = 10

# Default max aspect ratio (width:height) for text regions
# Regions with higher ratio are likely sentences/placeholders, not UI labels
# Value of 10.0 means skip regions wider than 10x their height (e.g., 170×13px = 13:1 ratio)
DEFAULT_MAX_ASPECT_RATIO = 10.0

# Default inference threads (-1 = auto, or set explicit count)
# Testing shows explicit thread count can be ~20% faster than auto
DEFAULT_INFERENCE_THREADS = -1


# Global cache for lazy loading (keyed by thread config)
_rapidocr_openvino_cache: Dict[int, "RapidOCR"] = {}


def _get_rapidocr_openvino(inference_threads: int = DEFAULT_INFERENCE_THREADS):
    """
    Get or create a RapidOCR-OpenVINO instance with specified thread configuration.

    Args:
        inference_threads: Number of threads for inference (-1 = auto-detect).
                          Higher values can improve throughput on multi-core CPUs.
                          Recommended: CPU_count or CPU_count * 2 for hyperthreaded CPUs.

    Returns:
        Configured RapidOCR instance
    """
    global _rapidocr_openvino_cache

    # Check environment variable override
    env_threads = os.environ.get('OCR_INFERENCE_THREADS')
    if env_threads is not None:
        try:
            inference_threads = int(env_threads)
        except ValueError:
            pass

    # Use cached instance if available for this thread config
    if inference_threads in _rapidocr_openvino_cache:
        return _rapidocr_openvino_cache[inference_threads]

    from rapidocr_openvino import RapidOCR

    # Pass optimizations at construction time for cleaner initialization
    # These settings are tuned for UI screenshot analysis (640x360 images)
    instance = RapidOCR(
        # OPTIMIZATION 1: Reduce detection resolution
        # Default limit_side_len=736 scales UP our 640x320 image
        # Setting to 320 avoids unnecessary upscaling
        # Speedup: ~4x faster detection (1000ms -> 270ms)
        det_limit_side_len=320,

        # OPTIMIZATION 2: Disable morphological dilation
        # Dilation expands text regions but adds processing time
        # For clean UI text, dilation is unnecessary
        # Speedup: ~20% faster detection
        det_use_dilation=False,

        # OPTIMIZATION 3: Reduce max text candidates
        # Default 1000 is overkill for UI screenshots (~30 text regions)
        # Reduces post-processing time
        det_max_candidates=200,

        # OPTIMIZATION 4: Increase recognition batch size
        # Default rec_batch_num=6 processes only 6 regions at a time
        # Note: Testing showed minimal impact, but keeps overhead low
        rec_batch_num=32,

        # OPTIMIZATION 5: Explicit thread configuration
        # Testing shows ~20% improvement with explicit threads vs auto (-1)
        # Set for both detection and recognition stages
        det_inference_num_threads=inference_threads,
        rec_inference_num_threads=inference_threads,
    )

    _rapidocr_openvino_cache[inference_threads] = instance

    thread_desc = "auto" if inference_threads == -1 else str(inference_threads)
    print(f"[OpenVINO-OCR] RapidOCR-OpenVINO instance created with speed optimizations:")
    print(f"  - det_limit_side_len=320 (faster detection)")
    print(f"  - det_use_dilation=False (skip morphological ops)")
    print(f"  - det_max_candidates=200 (faster post-processing)")
    print(f"  - rec_batch_num=32 (batch recognition)")
    print(f"  - inference_threads={thread_desc} (thread optimization)")

    return instance


class OpenVINOOCREngine:
    """
    OpenVINO-accelerated OCR engine using RapidOCR.

    RapidOCR uses PaddleOCR models pre-converted to OpenVINO format.
    This provides ~100-300ms inference time vs ~38s for native PaddleOCR.

    Features:
    - Uses pre-converted models (no conversion needed)
    - OpenVINO acceleration for fast CPU inference
    - Same accuracy as PaddleOCR (uses identical models)
    - Lazy loading with global cache
    """

    def __init__(
        self,
        language: str = "en",
        confidence_threshold: float = 0.5,
        device: str = "CPU",  # Kept for API compatibility, RapidOCR uses CPU
        max_regions: int = DEFAULT_MAX_REGIONS,  # Max text regions to recognize (0=unlimited)
        max_aspect_ratio: float = DEFAULT_MAX_ASPECT_RATIO,  # Skip wide regions (ratio > N)
        diagnostic_mode: bool = False,  # Enable per-region timing capture
        inference_threads: int = DEFAULT_INFERENCE_THREADS,  # Thread count for inference
    ):
        """
        Initialize the OpenVINO OCR engine.

        Args:
            language: Language code for OCR (e.g., 'en', 'ch')
            confidence_threshold: Minimum confidence for text detection
            device: OpenVINO device (currently only CPU supported by RapidOCR)
            max_regions: Maximum text regions to recognize (0=unlimited).
                         Larger boxes are prioritized as they're more likely
                         to contain important UI labels.
            max_aspect_ratio: Maximum width:height ratio for text regions.
                             Regions with higher ratio are skipped (likely sentences,
                             not UI labels). Set to 0 to disable. Default: 10.0
            diagnostic_mode: When True, captures per-region timing breakdown.
                            Adds ~10-20% overhead due to individual region processing.
            inference_threads: Number of threads for inference (-1 = auto-detect).
                              Testing shows explicit thread count can be ~20% faster.
                              Recommended: Set to CPU core count or higher.
        """
        self.language = language
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.max_regions = max_regions
        self.max_aspect_ratio = max_aspect_ratio
        self.diagnostic_mode = diagnostic_mode
        self.inference_threads = inference_threads
        self._ocr = None

    @property
    def ocr(self):
        """Lazy-load the RapidOCR-OpenVINO instance."""
        if self._ocr is None:
            self._ocr = _get_rapidocr_openvino(self.inference_threads)
        return self._ocr

    def extract_text(self, image: np.ndarray) -> OCRResult:
        """
        Extract text from an image using OpenVINO inference.

        Uses two-stage approach when max_regions is set:
        1. Run text detection to find all text boxes
        2. Filter to top N boxes by area (larger = more likely important)
        3. Run batch recognition only on filtered boxes

        Args:
            image: BGR or RGB numpy array

        Returns:
            OCRResult with detected TextRegions
        """
        start_time = time.perf_counter()

        # Use two-stage approach if max_regions is set
        if self.max_regions > 0:
            return self._extract_text_filtered(image, start_time)

        # Original full OCR approach (no filtering)
        return self._extract_text_full(image, start_time)

    def _extract_text_full(self, image: np.ndarray, start_time: float) -> OCRResult:
        """Full OCR without filtering (original approach)."""
        # RapidOCR expects BGR numpy array (same as OpenCV)
        # Returns: [[[bbox_points], text, confidence], ...]
        # use_cls=False: Skip text direction classifier (UI text is always upright)
        # elapse returns [detection_time, classification_time, recognition_time] in seconds
        result, elapse = self.ocr(image, use_cls=False)

        processing_time = (time.perf_counter() - start_time) * 1000

        # Extract detailed timing from elapse (in seconds, convert to ms)
        # elapse: [detection_time, classification_time, recognition_time]
        detection_time_ms = 0.0
        recognition_time_ms = 0.0
        if elapse and isinstance(elapse, (list, tuple)) and len(elapse) >= 3:
            detection_time_ms = elapse[0] * 1000  # Text detection phase
            recognition_time_ms = elapse[2] * 1000  # Text recognition phase (skip cls at [1])

        # Process results
        text_regions: List[TextRegion] = []

        if result:
            for item in result:
                # RapidOCR returns: [bbox_points, text, confidence]
                bbox_points, text, confidence = item

                if not text or not text.strip():
                    continue

                confidence = float(confidence)
                if confidence < self.confidence_threshold:
                    continue

                # bbox_points is [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
                # Convert to x1, y1, x2, y2
                xs = [p[0] for p in bbox_points]
                ys = [p[1] for p in bbox_points]

                bbox = BoundingBox(
                    x1=int(min(xs)),
                    y1=int(min(ys)),
                    x2=int(max(xs)),
                    y2=int(max(ys))
                )

                text_region = TextRegion(
                    text=text.strip(),
                    bbox=bbox,
                    confidence=confidence,
                    metadata={"engine": "rapidocr_openvino"}
                )
                text_regions.append(text_region)

        print(f"[OpenVINO-OCR] Extracted {len(text_regions)} text regions in {processing_time:.0f}ms (det={detection_time_ms:.0f}ms, rec={recognition_time_ms:.0f}ms)")

        return OCRResult(
            text_regions=text_regions,
            processing_time_ms=processing_time,
            language=self.language,
            detection_time_ms=detection_time_ms,
            recognition_time_ms=recognition_time_ms,
        )

    def _extract_text_filtered(self, image: np.ndarray, start_time: float) -> OCRResult:
        """
        Two-stage OCR with box filtering for faster recognition.

        Stage 1: Run text detection only (~500ms)
        Stage 2: Filter boxes by area, keep top N
        Stage 3: Run batch recognition on filtered boxes

        This reduces recognition time proportionally to the number of
        boxes filtered out.
        """
        ocr = self.ocr

        # Stage 1: Text detection only
        dt_boxes, det_time_s = ocr.text_det(image)
        detection_time_ms = det_time_s * 1000 if det_time_s else 0

        text_regions: List[TextRegion] = []
        region_timings: List[RecognitionRegionTiming] = []
        recognition_time_ms = 0.0

        if dt_boxes is not None and len(dt_boxes) > 0:
            total_detected = len(dt_boxes)

            # Stage 2: Filter boxes by aspect ratio and area
            # - Skip very wide regions (likely sentences/placeholders, not UI labels)
            # - Keep largest N boxes by area
            boxes_with_area = []
            aspect_ratio_skipped = 0

            for box in dt_boxes:
                xs, ys = box[:, 0], box[:, 1]
                width = xs.max() - xs.min()
                height = ys.max() - ys.min()
                area = width * height

                # Skip regions with extreme aspect ratio (width >> height)
                # These are likely long text strings like placeholders or sentences
                if self.max_aspect_ratio > 0 and height > 0:
                    aspect_ratio = width / height
                    if aspect_ratio > self.max_aspect_ratio:
                        aspect_ratio_skipped += 1
                        continue

                boxes_with_area.append((box, area))

            # Sort by area descending and keep top N
            boxes_with_area.sort(key=lambda x: x[1], reverse=True)
            filtered_boxes = [b[0] for b in boxes_with_area[:self.max_regions]]
            area_skipped = len(boxes_with_area) - len(filtered_boxes)
            total_skipped = aspect_ratio_skipped + area_skipped

            # Stage 3: Crop regions and run recognition
            if filtered_boxes:
                if self.diagnostic_mode:
                    # Diagnostic mode: process individually for per-region timing
                    text_regions, region_timings, recognition_time_ms = self._recognize_with_timing(
                        ocr, image, filtered_boxes
                    )
                else:
                    # Normal batch mode for performance
                    crop_list = ocr.get_crop_img_list(image, filtered_boxes)
                    rec_results, rec_time_s = ocr.text_rec(crop_list)
                    recognition_time_ms = rec_time_s * 1000 if rec_time_s else 0

                    # Combine boxes with recognition results
                    for i, (text, confidence) in enumerate(rec_results):
                        if not text or not text.strip():
                            continue

                        confidence = float(confidence)
                        if confidence < self.confidence_threshold:
                            continue

                        # Get bbox from filtered_boxes
                        box = filtered_boxes[i]
                        xs, ys = box[:, 0], box[:, 1]

                        bbox = BoundingBox(
                            x1=int(xs.min()),
                            y1=int(ys.min()),
                            x2=int(xs.max()),
                            y2=int(ys.max())
                        )

                        text_region = TextRegion(
                            text=text.strip(),
                            bbox=bbox,
                            confidence=confidence,
                            metadata={"engine": "rapidocr_openvino", "filtered": True}
                        )
                        text_regions.append(text_region)

            skip_details = []
            if aspect_ratio_skipped > 0:
                skip_details.append(f"{aspect_ratio_skipped} wide")
            if area_skipped > 0:
                skip_details.append(f"{area_skipped} small")
            skip_info = f" (skipped: {', '.join(skip_details)})" if skip_details else ""
            print(f"[OpenVINO-OCR] Filtered: {total_detected} detected -> {len(filtered_boxes)} recognized{skip_info}")

        processing_time = (time.perf_counter() - start_time) * 1000

        diag_info = f" [DIAGNOSTIC: {len(region_timings)} regions]" if self.diagnostic_mode else ""
        print(f"[OpenVINO-OCR] Extracted {len(text_regions)} text regions in {processing_time:.0f}ms (det={detection_time_ms:.0f}ms, rec={recognition_time_ms:.0f}ms){diag_info}")

        return OCRResult(
            text_regions=text_regions,
            processing_time_ms=processing_time,
            language=self.language,
            detection_time_ms=detection_time_ms,
            recognition_time_ms=recognition_time_ms,
            region_timings=region_timings if region_timings else None,
        )

    def _recognize_with_timing(
        self,
        ocr,
        image: np.ndarray,
        filtered_boxes: List
    ) -> Tuple[List[TextRegion], List[RecognitionRegionTiming], float]:
        """
        Process text recognition with per-region timing capture.

        Args:
            ocr: RapidOCR instance
            image: Source image
            filtered_boxes: List of detected text boxes to recognize

        Returns:
            Tuple of (text_regions, region_timings, total_recognition_time_ms)
        """
        text_regions: List[TextRegion] = []
        region_timings: List[RecognitionRegionTiming] = []
        total_rec_time = 0.0

        for i, box in enumerate(filtered_boxes):
            xs, ys = box[:, 0], box[:, 1]
            crop_width = int(xs.max() - xs.min())
            crop_height = int(ys.max() - ys.min())

            # Time: Crop extraction (preprocessing)
            preprocess_start = time.perf_counter()
            crop_list = ocr.get_crop_img_list(image, [box])
            preprocess_ms = (time.perf_counter() - preprocess_start) * 1000

            # Time: Recognition (inference + decode combined in RapidOCR)
            inference_start = time.perf_counter()
            rec_results, rec_time_s = ocr.text_rec(crop_list)
            inference_ms = (time.perf_counter() - inference_start) * 1000

            # RapidOCR combines inference and decode, so we estimate decode as ~10% of total
            # This is an approximation based on typical CRNN behavior
            decode_ms = inference_ms * 0.1
            actual_inference_ms = inference_ms * 0.9

            total_ms = preprocess_ms + inference_ms
            total_rec_time += inference_ms

            # Get recognition result
            text = ""
            confidence = 0.0
            if rec_results and len(rec_results) > 0:
                text, confidence = rec_results[0]
                text = text.strip() if text else ""
                confidence = float(confidence)

            # Store timing regardless of confidence (for diagnostics)
            timing = RecognitionRegionTiming(
                region_index=i,
                crop_width=crop_width,
                crop_height=crop_height,
                preprocess_ms=preprocess_ms,
                inference_ms=actual_inference_ms,
                decode_ms=decode_ms,
                total_ms=total_ms,
                text=text,
                confidence=confidence,
            )
            region_timings.append(timing)

            # Only add to text_regions if meets threshold
            if text and confidence >= self.confidence_threshold:
                bbox = BoundingBox(
                    x1=int(xs.min()),
                    y1=int(ys.min()),
                    x2=int(xs.max()),
                    y2=int(ys.max())
                )
                text_region = TextRegion(
                    text=text,
                    bbox=bbox,
                    confidence=confidence,
                    metadata={"engine": "rapidocr_openvino", "filtered": True, "region_index": i}
                )
                text_regions.append(text_region)

        return text_regions, region_timings, total_rec_time

    def extract_text_from_region(
        self,
        image: np.ndarray,
        bbox: BoundingBox
    ) -> OCRResult:
        """
        Extract text from a specific region of an image.

        Args:
            image: BGR or RGB numpy array
            bbox: Region to extract text from

        Returns:
            OCRResult with text from the specified region
        """
        # Crop the region
        cropped = image[bbox.y1:bbox.y2, bbox.x1:bbox.x2]

        # Run OCR on cropped region
        result = self.extract_text(cropped)

        # Adjust coordinates to original image space
        adjusted_regions = []
        for region in result.text_regions:
            adjusted_bbox = BoundingBox(
                x1=region.bbox.x1 + bbox.x1,
                y1=region.bbox.y1 + bbox.y1,
                x2=region.bbox.x2 + bbox.x1,
                y2=region.bbox.y2 + bbox.y1
            )
            adjusted_region = TextRegion(
                text=region.text,
                bbox=adjusted_bbox,
                confidence=region.confidence,
                metadata=region.metadata
            )
            adjusted_regions.append(adjusted_region)

        return OCRResult(
            text_regions=adjusted_regions,
            processing_time_ms=result.processing_time_ms,
            language=result.language,
            detection_time_ms=result.detection_time_ms,
            recognition_time_ms=result.recognition_time_ms,
        )

    def get_engine_info(self) -> Dict:
        """Get information about the OCR engine."""
        return {
            "engine": "rapidocr_openvino",
            "language": self.language,
            "device": self.device,
            "confidence_threshold": self.confidence_threshold,
            "max_regions": self.max_regions,
            "max_aspect_ratio": self.max_aspect_ratio,
            "filtering_enabled": self.max_regions > 0 or self.max_aspect_ratio > 0,
            "diagnostic_mode": self.diagnostic_mode,
            "inference_threads": self.inference_threads,
            "loaded": self._ocr is not None,
        }

    def is_loaded(self) -> bool:
        """Check if OCR engine is loaded."""
        return self._ocr is not None


def create_openvino_ocr_engine_from_settings(settings, diagnostic_mode: bool = False) -> OpenVINOOCREngine:
    """
    Factory function to create OpenVINO OCR engine from app settings.

    Args:
        settings: Application settings object
        diagnostic_mode: Enable per-region timing capture

    Returns:
        Configured OpenVINOOCREngine
    """
    device = getattr(settings, 'PADDLEOCR_OPENVINO_DEVICE', 'CPU')
    max_regions = getattr(settings, 'OCR_MAX_REGIONS', DEFAULT_MAX_REGIONS)
    max_aspect_ratio = getattr(settings, 'OCR_MAX_ASPECT_RATIO', DEFAULT_MAX_ASPECT_RATIO)
    inference_threads = getattr(settings, 'OCR_INFERENCE_THREADS', DEFAULT_INFERENCE_THREADS)

    return OpenVINOOCREngine(
        language=settings.OCR_LANGUAGE,
        confidence_threshold=settings.OCR_CONFIDENCE_THRESHOLD,
        device=device,
        max_regions=max_regions,
        max_aspect_ratio=max_aspect_ratio,
        diagnostic_mode=diagnostic_mode,
        inference_threads=inference_threads,
    )
