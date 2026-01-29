"""
PaddleOCR Text Extraction Engine

Uses PaddleOCR for fast text extraction from screenshots.
Significantly faster than EasyOCR, especially on CPU.
Implements lazy model loading with global cache.
"""

import os
import time
from typing import Dict, List, Optional

import numpy as np

# Disable PaddleOCR's connectivity check to avoid network delays
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"
# Disable PaddlePaddle verbose logging
os.environ["GLOG_minloglevel"] = "2"

from .data_classes import BoundingBox, TextRegion, OCRResult


# Global OCR reader cache for lazy loading
_paddle_ocr_cache: Dict[str, "PaddleOCR"] = {}


def _get_paddle_ocr(
    language: str = "en",
    use_gpu: bool = False,
    use_angle_cls: bool = False
) -> "PaddleOCR":
    """
    Get or load PaddleOCR instance with caching.

    PaddleOCR instances are loaded on first use and cached globally.
    Uses PP-OCRv4 mobile models for optimal speed.

    Args:
        language: Language code (e.g., 'en', 'ch')
        use_gpu: Whether to use GPU acceleration
        use_angle_cls: Whether to use angle classification (slower)

    Returns:
        Loaded PaddleOCR instance
    """
    global _paddle_ocr_cache

    cache_key = f"{language}_{use_gpu}_{use_angle_cls}"

    if cache_key not in _paddle_ocr_cache:
        from paddleocr import PaddleOCR

        # PaddleOCR 3.x uses 'device' instead of 'use_gpu'
        # device: 'gpu' or 'cpu'
        device = "gpu" if use_gpu else "cpu"

        # Use mobile models for speed, disable unnecessary features
        # PaddleOCR 3.x removed show_log parameter
        # IMPORTANT: Explicitly specify mobile models to avoid slow server models
        # Map language to mobile rec model name
        rec_model = f"{language}_PP-OCRv5_mobile_rec" if language != "ch" else "ch_PP-OCRv5_mobile_rec"

        _paddle_ocr_cache[cache_key] = PaddleOCR(
            lang=language,
            use_angle_cls=use_angle_cls,
            device=device,
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name=rec_model,
            # Disable document preprocessing to speed up inference
            # These are designed for document images and add ~10-20 seconds of overhead
            use_doc_orientation_classify=False,  # Disable document orientation detection
            use_doc_unwarping=False,  # Disable document unwarping (UVDoc)
        )

    return _paddle_ocr_cache[cache_key]


class PaddleOCREngine:
    """
    PaddleOCR based text extraction engine.

    Extracts text and positions from images using PaddleOCR.
    Much faster than EasyOCR, especially on CPU (~10-50x faster).
    Reader is lazily loaded on first extraction.
    """

    def __init__(
        self,
        language: str = "en",
        use_gpu: bool = False,
        confidence_threshold: float = 0.5,
        use_angle_cls: bool = False
    ):
        """
        Initialize the PaddleOCR engine.

        Args:
            language: Language code for OCR (default: "en")
            use_gpu: Whether to use GPU acceleration
            confidence_threshold: Minimum confidence for text detection
            use_angle_cls: Whether to use angle classification (slower but handles rotated text)
        """
        self.language = language
        self.use_gpu = use_gpu
        self.confidence_threshold = confidence_threshold
        self.use_angle_cls = use_angle_cls
        self._reader = None

    @property
    def reader(self):
        """Lazy-load the PaddleOCR reader."""
        if self._reader is None:
            self._reader = _get_paddle_ocr(
                self.language,
                self.use_gpu,
                self.use_angle_cls
            )
        return self._reader

    def extract_text(
        self,
        image: np.ndarray,
    ) -> OCRResult:
        """
        Extract text from an image.

        Args:
            image: BGR or RGB numpy array

        Returns:
            OCRResult with detected TextRegions
        """
        start_time = time.perf_counter()

        # PaddleOCR 3.x uses predict() instead of ocr()
        # Returns list of results per image
        # Format: [[[x1,y1], [x2,y1], [x2,y2], [x1,y2]], ('text', confidence)]
        predict_start = time.perf_counter()
        results = self.reader.predict(image)
        predict_time = (time.perf_counter() - predict_start) * 1000
        print(f"[PaddleOCR] predict() took {predict_time:.0f}ms")

        # Process results
        text_regions: List[TextRegion] = []

        # PaddleOCR 3.x returns a list of dictionaries with 'rec_texts', 'rec_scores', 'dt_polys'
        # Each dict represents results for one image
        if results:
            for result in results:
                if result is None:
                    continue

                # PaddleOCR 3.x format: dict with 'rec_texts', 'rec_scores', 'dt_polys'
                if isinstance(result, dict):
                    rec_texts = result.get('rec_texts', [])
                    rec_scores = result.get('rec_scores', [])
                    dt_polys = result.get('dt_polys', [])

                    for text, confidence, polygon in zip(rec_texts, rec_scores, dt_polys):
                        confidence = float(confidence)

                        # Skip low confidence detections
                        if confidence < self.confidence_threshold:
                            continue

                        # Convert polygon to bounding box
                        bbox = self._polygon_to_bbox(polygon)

                        text_region = TextRegion(
                            text=text,
                            bbox=bbox,
                            confidence=confidence,
                            metadata={"engine": "paddleocr"}
                        )
                        text_regions.append(text_region)
                else:
                    # Legacy format fallback: [[polygon, (text, confidence)], ...]
                    detections = result if isinstance(result, list) else [result]
                    for detection in detections:
                        if detection is None:
                            continue

                        bbox_points = detection[0]
                        text_info = detection[1]

                        if text_info is None:
                            continue

                        text = text_info[0]
                        confidence = float(text_info[1])

                        if confidence < self.confidence_threshold:
                            continue

                        bbox = self._polygon_to_bbox(bbox_points)

                        text_region = TextRegion(
                            text=text,
                            bbox=bbox,
                            confidence=confidence,
                            metadata={"engine": "paddleocr"}
                        )
                        text_regions.append(text_region)

        processing_time = (time.perf_counter() - start_time) * 1000  # Convert to ms

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

    def _polygon_to_bbox(self, points: List[List[float]]) -> BoundingBox:
        """
        Convert polygon points to bounding box.

        PaddleOCR returns 4 corner points: [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]

        Args:
            points: List of [x, y] coordinate pairs

        Returns:
            BoundingBox encompassing all points
        """
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]

        return BoundingBox(
            x1=int(min(x_coords)),
            y1=int(min(y_coords)),
            x2=int(max(x_coords)),
            y2=int(max(y_coords))
        )

    def get_engine_info(self) -> Dict:
        """
        Get information about the OCR engine.

        Returns:
            Dictionary with engine details
        """
        return {
            "engine": "paddleocr",
            "language": self.language,
            "use_gpu": self.use_gpu,
            "confidence_threshold": self.confidence_threshold,
            "use_angle_cls": self.use_angle_cls,
            "loaded": self._reader is not None
        }

    def is_loaded(self) -> bool:
        """Check if reader is loaded."""
        return self._reader is not None


def create_paddle_ocr_engine_from_settings(settings) -> PaddleOCREngine:
    """
    Factory function to create PaddleOCR engine from app settings.

    Args:
        settings: Application settings object

    Returns:
        Configured PaddleOCREngine
    """
    return PaddleOCREngine(
        language=settings.OCR_LANGUAGE,
        use_gpu=settings.OCR_USE_GPU,
        confidence_threshold=settings.OCR_CONFIDENCE_THRESHOLD,
        use_angle_cls=getattr(settings, 'PADDLEOCR_USE_ANGLE_CLS', False)
    )
