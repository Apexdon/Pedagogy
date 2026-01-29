"""
CV Pipeline Package

Computer Vision pipeline for processing screenshots to detect UI elements
and extract text, combining them into unified screen state representations.

Components:
- ImagePreprocessor: Image decoding, validation, and resizing
- OmniParserDetector: Microsoft OmniParser v2 for UI element detection (recommended, with OpenVINO acceleration)
- YOLODetector: YOLO v11 based UI element detection (legacy fallback)
- SuryaOCREngine: Surya OCR text extraction (fast + accurate, recommended, ~300-500ms)
- PaddleOCREngine: PaddleOCR based text extraction (accurate, ~5-10s)
- OCREngine: EasyOCR based text extraction (legacy fallback)
- FastOCREngine: RapidOCR/Tesseract for fast verification (~200-400ms)
- ContextEngine: Fusion layer that combines detection and OCR (with parallel processing)
"""

from .data_classes import (
    BoundingBox,
    UIElement,
    TextRegion,
    DetectionResult,
    OCRResult,
    ScreenState
)

from .preprocessor import ImagePreprocessor, PreprocessedImage

from .yolo_detector import (
    YOLODetector,
    create_detector_from_settings as create_yolo_detector_from_settings
)

from .omniparser_detector import (
    OmniParserDetector,
    create_omniparser_detector_from_settings
)

from .ocr_engine import (
    OCREngine,
    create_ocr_engine_from_settings
)

from .paddle_ocr_engine import (
    PaddleOCREngine,
    create_paddle_ocr_engine_from_settings
)

from .fast_ocr_engine import (
    FastOCREngine,
    get_fast_ocr_engine,
    create_fast_ocr_engine_from_settings
)

from .surya_ocr_engine import (
    SuryaOCREngine,
    get_surya_ocr_engine,
    create_surya_ocr_engine_from_settings
)

from .context_engine import (
    ContextEngine,
    create_context_engine_from_settings
)

from .scroll_detector import (
    ScrollOffsetDetector,
    ScrollDetectionResult,
    get_scroll_detector,
    apply_scroll_offset_to_bbox
)


def create_detector_from_settings(settings):
    """
    Factory function to create the appropriate detector based on settings.

    Uses OmniParser by default (better UI detection), falls back to YOLO
    if OmniParser models are not available.
    """
    import os

    if settings.CV_DETECTION_BACKEND == "omniparser":
        # Check if OmniParser models exist
        icon_detect_path = settings.OMNIPARSER_ICON_DETECT_PATH
        if os.path.exists(icon_detect_path):
            return create_omniparser_detector_from_settings(settings)
        else:
            print(f"OmniParser model not found at {icon_detect_path}, falling back to YOLO")
            return create_yolo_detector_from_settings(settings)
    else:
        return create_yolo_detector_from_settings(settings)


__all__ = [
    # Data classes
    "BoundingBox",
    "UIElement",
    "TextRegion",
    "DetectionResult",
    "OCRResult",
    "ScreenState",
    # Preprocessor
    "ImagePreprocessor",
    "PreprocessedImage",
    # Detectors
    "OmniParserDetector",
    "create_omniparser_detector_from_settings",
    "YOLODetector",
    "create_yolo_detector_from_settings",
    "create_detector_from_settings",
    # OCR Engines
    "SuryaOCREngine",
    "get_surya_ocr_engine",
    "create_surya_ocr_engine_from_settings",
    "PaddleOCREngine",
    "create_paddle_ocr_engine_from_settings",
    "OCREngine",
    "create_ocr_engine_from_settings",
    "FastOCREngine",
    "get_fast_ocr_engine",
    "create_fast_ocr_engine_from_settings",
    # Context Engine
    "ContextEngine",
    "create_context_engine_from_settings",
    # Scroll Detector
    "ScrollOffsetDetector",
    "ScrollDetectionResult",
    "get_scroll_detector",
    "apply_scroll_offset_to_bbox",
]
