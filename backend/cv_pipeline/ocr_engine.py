"""
EasyOCR Text Extraction Engine

Uses EasyOCR for extracting text from screenshots.
Implements lazy model loading with global cache.
"""

import time
from typing import Dict, List, Optional, Tuple

import numpy as np

from .data_classes import BoundingBox, TextRegion, OCRResult


# Global OCR reader cache for lazy loading
_ocr_reader_cache: Dict[str, "easyocr.Reader"] = {}


def _get_ocr_reader(languages: List[str], use_gpu: bool = False) -> "easyocr.Reader":
    """
    Get or load EasyOCR Reader with caching.

    Readers are loaded on first use and cached globally.
    Language models are downloaded automatically on first use.

    Args:
        languages: List of language codes (e.g., ['en'])
        use_gpu: Whether to use GPU acceleration

    Returns:
        Loaded EasyOCR Reader
    """
    global _ocr_reader_cache

    cache_key = f"{','.join(sorted(languages))}_{use_gpu}"

    if cache_key not in _ocr_reader_cache:
        import easyocr
        _ocr_reader_cache[cache_key] = easyocr.Reader(
            languages,
            gpu=use_gpu,
            verbose=False
        )

    return _ocr_reader_cache[cache_key]


class OCREngine:
    """
    EasyOCR based text extraction engine.

    Extracts text and positions from images using EasyOCR.
    Reader is lazily loaded on first extraction.
    """

    def __init__(
        self,
        language: str = "en",
        use_gpu: bool = False,
        confidence_threshold: float = 0.6
    ):
        """
        Initialize the OCR engine.

        Args:
            language: Language code for OCR (default: "en")
            use_gpu: Whether to use GPU acceleration
            confidence_threshold: Minimum confidence for text detection
        """
        self.language = language
        self.languages = [language]  # EasyOCR expects list
        self.use_gpu = use_gpu
        self.confidence_threshold = confidence_threshold
        self._reader = None

    @property
    def reader(self):
        """Lazy-load the EasyOCR reader."""
        if self._reader is None:
            self._reader = _get_ocr_reader(self.languages, self.use_gpu)
        return self._reader

    def extract_text(
        self,
        image: np.ndarray,
        detail: int = 1
    ) -> OCRResult:
        """
        Extract text from an image.

        Args:
            image: BGR or RGB numpy array
            detail: 0 for simple output, 1 for detailed with boxes

        Returns:
            OCRResult with detected TextRegions
        """
        start_time = time.perf_counter()

        # Run OCR
        # EasyOCR returns: [[bbox_points], text, confidence]
        results = self.reader.readtext(image, detail=detail)

        # Process results
        text_regions: List[TextRegion] = []

        for detection in results:
            if detail == 1:
                # Detailed mode: [[x1,y1], [x2,y1], [x2,y2], [x1,y2]], text, confidence
                bbox_points, text, confidence = detection

                # Skip low confidence detections
                if confidence < self.confidence_threshold:
                    continue

                # Convert polygon to bounding box
                bbox = self._polygon_to_bbox(bbox_points)
            else:
                # Simple mode: just text
                text = detection
                confidence = 1.0
                bbox = BoundingBox(0, 0, 0, 0)

            text_region = TextRegion(
                text=text,
                bbox=bbox,
                confidence=confidence,
                metadata={}
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

        EasyOCR returns 4 corner points: [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]

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
            "engine": "easyocr",
            "language": self.language,
            "use_gpu": self.use_gpu,
            "confidence_threshold": self.confidence_threshold,
            "loaded": self._reader is not None
        }

    def is_loaded(self) -> bool:
        """Check if reader is loaded."""
        return self._reader is not None


def create_ocr_engine_from_settings(settings) -> OCREngine:
    """
    Factory function to create OCR engine from app settings.

    Args:
        settings: Application settings object

    Returns:
        Configured OCREngine
    """
    return OCREngine(
        language=settings.OCR_LANGUAGE,
        use_gpu=settings.OCR_USE_GPU,
        confidence_threshold=settings.OCR_CONFIDENCE_THRESHOLD
    )
