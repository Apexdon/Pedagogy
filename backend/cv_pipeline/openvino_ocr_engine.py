"""
OpenVINO-Accelerated OCR Engine

Uses RapidOCR with OpenVINO backend for fast text extraction.
RapidOCR uses PaddleOCR models pre-converted to ONNX/OpenVINO format.

Performance: ~100-300ms (vs ~38s for native PaddleOCR)
"""

import time
from typing import Dict, List, Optional

import numpy as np

from .data_classes import BoundingBox, TextRegion, OCRResult


# Global cache for lazy loading
_rapidocr_openvino_instance = None


def _get_rapidocr_openvino():
    """Get or create the global RapidOCR-OpenVINO instance."""
    global _rapidocr_openvino_instance

    if _rapidocr_openvino_instance is None:
        from rapidocr_openvino import RapidOCR
        _rapidocr_openvino_instance = RapidOCR()
        print("[OpenVINO-OCR] RapidOCR-OpenVINO instance created")

    return _rapidocr_openvino_instance


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
    ):
        """
        Initialize the OpenVINO OCR engine.

        Args:
            language: Language code for OCR (e.g., 'en', 'ch')
            confidence_threshold: Minimum confidence for text detection
            device: OpenVINO device (currently only CPU supported by RapidOCR)
        """
        self.language = language
        self.confidence_threshold = confidence_threshold
        self.device = device
        self._ocr = None

    @property
    def ocr(self):
        """Lazy-load the RapidOCR-OpenVINO instance."""
        if self._ocr is None:
            self._ocr = _get_rapidocr_openvino()
        return self._ocr

    def extract_text(self, image: np.ndarray) -> OCRResult:
        """
        Extract text from an image using OpenVINO inference.

        Args:
            image: BGR or RGB numpy array

        Returns:
            OCRResult with detected TextRegions
        """
        start_time = time.perf_counter()

        # RapidOCR expects BGR numpy array (same as OpenCV)
        # Returns: [[[bbox_points], text, confidence], ...]
        result, elapse = self.ocr(image)

        processing_time = (time.perf_counter() - start_time) * 1000

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

        print(f"[OpenVINO-OCR] Extracted {len(text_regions)} text regions in {processing_time:.0f}ms")

        return OCRResult(
            text_regions=text_regions,
            processing_time_ms=processing_time,
            language=self.language
        )

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
            language=result.language
        )

    def get_engine_info(self) -> Dict:
        """Get information about the OCR engine."""
        return {
            "engine": "rapidocr_openvino",
            "language": self.language,
            "device": self.device,
            "confidence_threshold": self.confidence_threshold,
            "loaded": self._ocr is not None,
        }

    def is_loaded(self) -> bool:
        """Check if OCR engine is loaded."""
        return self._ocr is not None


def create_openvino_ocr_engine_from_settings(settings) -> OpenVINOOCREngine:
    """
    Factory function to create OpenVINO OCR engine from app settings.

    Args:
        settings: Application settings object

    Returns:
        Configured OpenVINOOCREngine
    """
    device = getattr(settings, 'PADDLEOCR_OPENVINO_DEVICE', 'CPU')

    return OpenVINOOCREngine(
        language=settings.OCR_LANGUAGE,
        confidence_threshold=settings.OCR_CONFIDENCE_THRESHOLD,
        device=device,
    )
