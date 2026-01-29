"""
Surya OCR Text Extraction Engine

Uses Surya OCR for high-accuracy, fast text extraction from screenshots.
Surya offers excellent accuracy comparable to PaddleOCR but with faster inference.
Implements lazy model loading with global cache.

Performance:
- Speed: ~300-500ms per image (vs ~5-10s for PaddleOCR)
- Accuracy: Excellent, comparable to PaddleOCR
- GPU: Supports CUDA acceleration
"""

import time
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from .data_classes import BoundingBox, TextRegion, OCRResult


# Global predictor cache for lazy loading
_surya_predictors: Dict[str, any] = {}
_surya_available: Optional[bool] = None


def _check_surya_available() -> bool:
    """Check if Surya OCR is available."""
    global _surya_available

    if _surya_available is not None:
        return _surya_available

    try:
        from surya.recognition import RecognitionPredictor
        from surya.detection import DetectionPredictor
        from surya.foundation import FoundationPredictor
        _surya_available = True
        print("[SuryaOCR] Surya OCR is available (v0.17+ API)")
        return True
    except ImportError as e:
        print(f"[SuryaOCR] Surya OCR not available: {e}")
        _surya_available = False
        return False
    except Exception as e:
        print(f"[SuryaOCR] Error checking Surya OCR: {e}")
        _surya_available = False
        return False


def _get_surya_predictors() -> Tuple[any, any]:
    """
    Get or load Surya predictors with caching.

    Predictors are loaded on first use and cached globally.
    Models are downloaded automatically on first use.

    Returns:
        Tuple of (recognition_predictor, detection_predictor)
    """
    global _surya_predictors

    if "recognition" not in _surya_predictors:
        print("[SuryaOCR] Loading Surya models (first time may download ~1GB)...")
        load_start = time.perf_counter()

        from surya.recognition import RecognitionPredictor
        from surya.detection import DetectionPredictor
        from surya.foundation import FoundationPredictor

        # Load foundation predictor first (required by RecognitionPredictor in Surya 0.17+)
        foundation_predictor = FoundationPredictor()

        # DetectionPredictor uses checkpoint, not foundation_predictor
        # RecognitionPredictor requires foundation_predictor
        detection_predictor = DetectionPredictor()  # Uses default checkpoint
        recognition_predictor = RecognitionPredictor(foundation_predictor)

        _surya_predictors["foundation"] = foundation_predictor
        _surya_predictors["detection"] = detection_predictor
        _surya_predictors["recognition"] = recognition_predictor

        load_time = (time.perf_counter() - load_start) * 1000
        print(f"[SuryaOCR] Models loaded in {load_time:.0f}ms")

    return _surya_predictors["recognition"], _surya_predictors["detection"]


class SuryaOCREngine:
    """
    Surya OCR based text extraction engine.

    Extracts text and positions from images using Surya OCR.
    Offers excellent accuracy with faster inference than PaddleOCR.
    Predictors are lazily loaded on first extraction.
    """

    def __init__(
        self,
        language: str = "en",
        confidence_threshold: float = 0.5,
    ):
        """
        Initialize the Surya OCR engine.

        Args:
            language: Language code for OCR (default: "en")
            confidence_threshold: Minimum confidence for text detection
        """
        self.language = language
        self.confidence_threshold = confidence_threshold
        self._recognition_predictor = None
        self._detection_predictor = None
        self._initialized = False

    def _ensure_initialized(self) -> bool:
        """Ensure predictors are loaded."""
        if self._initialized:
            return True

        if not _check_surya_available():
            return False

        self._recognition_predictor, self._detection_predictor = _get_surya_predictors()
        self._initialized = True
        return True

    def is_available(self) -> bool:
        """Check if Surya OCR is available."""
        return _check_surya_available()

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
        if not self._ensure_initialized():
            print("[SuryaOCR] Surya not available, returning empty result")
            return OCRResult(
                text_regions=[],
                processing_time_ms=0,
                language=self.language
            )

        start_time = time.perf_counter()

        # Convert numpy array to PIL Image
        if len(image.shape) == 3 and image.shape[2] == 3:
            # Assume BGR from OpenCV, convert to RGB
            pil_image = Image.fromarray(image[:, :, ::-1])
        else:
            pil_image = Image.fromarray(image)

        # Get image dimensions for coordinate scaling
        img_width, img_height = pil_image.size

        # Run Surya OCR
        predict_start = time.perf_counter()

        # Surya returns predictions with text lines
        predictions = self._recognition_predictor(
            [pil_image],
            det_predictor=self._detection_predictor
        )

        predict_time = (time.perf_counter() - predict_start) * 1000
        print(f"[SuryaOCR] Recognition took {predict_time:.0f}ms")

        # Process results
        text_regions: List[TextRegion] = []

        if predictions and len(predictions) > 0:
            # predictions is a list of OCRResult objects (one per image)
            ocr_result = predictions[0]

            # Access text lines from the result
            if hasattr(ocr_result, 'text_lines'):
                for line in ocr_result.text_lines:
                    text = line.text if hasattr(line, 'text') else ""
                    confidence = line.confidence if hasattr(line, 'confidence') else 0.0

                    # Skip empty text or low confidence
                    if not text or not text.strip():
                        continue

                    if confidence < self.confidence_threshold:
                        continue

                    # Get bounding box
                    # Surya uses bbox format: [x1, y1, x2, y2]
                    if hasattr(line, 'bbox'):
                        bbox_coords = line.bbox
                        bbox = BoundingBox(
                            x1=int(bbox_coords[0]),
                            y1=int(bbox_coords[1]),
                            x2=int(bbox_coords[2]),
                            y2=int(bbox_coords[3])
                        )
                    elif hasattr(line, 'polygon'):
                        # Convert polygon to bbox
                        bbox = self._polygon_to_bbox(line.polygon)
                    else:
                        # Fallback: use full image width
                        bbox = BoundingBox(x1=0, y1=0, x2=img_width, y2=20)

                    text_region = TextRegion(
                        text=text.strip(),
                        bbox=bbox,
                        confidence=float(confidence),
                        metadata={"engine": "surya"}
                    )
                    text_regions.append(text_region)

        processing_time = (time.perf_counter() - start_time) * 1000

        print(f"[SuryaOCR] Total: {processing_time:.0f}ms, found {len(text_regions)} text regions")

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

    def _polygon_to_bbox(self, polygon: List) -> BoundingBox:
        """Convert polygon points to bounding box."""
        if not polygon:
            return BoundingBox(x1=0, y1=0, x2=100, y2=20)

        # Handle different polygon formats
        if isinstance(polygon[0], (list, tuple)):
            xs = [p[0] for p in polygon]
            ys = [p[1] for p in polygon]
        else:
            # Flat list: [x1, y1, x2, y2, ...]
            xs = polygon[0::2]
            ys = polygon[1::2]

        return BoundingBox(
            x1=int(min(xs)),
            y1=int(min(ys)),
            x2=int(max(xs)),
            y2=int(max(ys))
        )

    def get_engine_info(self) -> Dict:
        """Get information about the OCR engine."""
        return {
            "engine": "surya",
            "language": self.language,
            "confidence_threshold": self.confidence_threshold,
            "initialized": self._initialized,
            "available": _check_surya_available()
        }

    def is_loaded(self) -> bool:
        """Check if engine is initialized."""
        return self._initialized


# Global Surya OCR instance (lazy loaded)
_surya_ocr_instance: Optional[SuryaOCREngine] = None


def get_surya_ocr_engine(settings=None) -> SuryaOCREngine:
    """
    Get or create the global Surya OCR engine instance.

    Args:
        settings: Optional app settings for configuration

    Returns:
        SuryaOCREngine instance
    """
    global _surya_ocr_instance

    if _surya_ocr_instance is None:
        language = "en"
        confidence_threshold = 0.5

        if settings:
            if hasattr(settings, 'SURYA_OCR_LANGUAGE'):
                language = settings.SURYA_OCR_LANGUAGE
            if hasattr(settings, 'SURYA_OCR_CONFIDENCE_THRESHOLD'):
                confidence_threshold = settings.SURYA_OCR_CONFIDENCE_THRESHOLD

        _surya_ocr_instance = SuryaOCREngine(
            language=language,
            confidence_threshold=confidence_threshold,
        )

    return _surya_ocr_instance


def create_surya_ocr_engine_from_settings(settings) -> SuryaOCREngine:
    """
    Factory function to create Surya OCR engine from app settings.

    Args:
        settings: Application settings object

    Returns:
        Configured SuryaOCREngine
    """
    return SuryaOCREngine(
        language=getattr(settings, 'SURYA_OCR_LANGUAGE', 'en'),
        confidence_threshold=getattr(settings, 'SURYA_OCR_CONFIDENCE_THRESHOLD', 0.5),
    )
