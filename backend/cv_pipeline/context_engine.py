"""
Context Engine - Fusion Layer for CV Pipeline

Combines UI detection (OmniParser or YOLO) and OCR text extraction
(PaddleOCR or EasyOCR) into a unified screen state representation.

Supports parallel processing for improved performance.
"""

import concurrent.futures
import time
import uuid
from datetime import datetime
from typing import List, Optional, Tuple, Union

import numpy as np

from .data_classes import (
    BoundingBox,
    UIElement,
    TextRegion,
    DetectionResult,
    OCRResult,
    ScreenState
)
from .preprocessor import ImagePreprocessor, PreprocessedImage
from .yolo_detector import YOLODetector
from .ocr_engine import OCREngine


class ContextEngine:
    """
    Unified CV analysis engine that combines UI detection and OCR.

    Coordinates the preprocessing, detection, OCR, and fusion
    of results into a complete screen state representation.

    Supports both OmniParser (recommended) and YOLO (legacy) detectors.
    """

    def __init__(
        self,
        preprocessor: ImagePreprocessor,
        detector,  # Can be OmniParserDetector or YOLODetector
        ocr_engine: OCREngine
    ):
        """
        Initialize the context engine.

        Args:
            preprocessor: Image preprocessor instance
            detector: UI detector instance (OmniParserDetector or YOLODetector)
            ocr_engine: OCR engine instance
        """
        self.preprocessor = preprocessor
        self.detector = detector
        self.ocr_engine = ocr_engine

    def analyze(
        self,
        base64_image: str,
        resize: bool = True,
        fuse_labels: bool = True
    ) -> ScreenState:
        """
        Full analysis pipeline: preprocess -> detect -> OCR -> fuse.

        Args:
            base64_image: Base64 encoded image string
            resize: Whether to resize large images
            fuse_labels: Whether to associate text with UI elements

        Returns:
            Complete ScreenState with elements and text
        """
        start_time = time.perf_counter()

        # Preprocess image
        preprocess_start = time.perf_counter()
        preprocessed = self.preprocessor.preprocess(base64_image, resize=resize)
        preprocess_time = (time.perf_counter() - preprocess_start) * 1000
        print(f"[ContextEngine] Preprocess took {preprocess_time:.0f}ms")

        # Run detection and OCR in parallel
        # Note: On older CPUs (like i7-3520M), this is still slow but better than sequential
        parallel_start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            detection_future = executor.submit(self.detector.detect, preprocessed.image)
            ocr_future = executor.submit(self.ocr_engine.extract_text, preprocessed.image)

            detection_result = detection_future.result()
            ocr_result = ocr_future.result()
        parallel_time = (time.perf_counter() - parallel_start) * 1000

        print(f"[ContextEngine] Detection found {len(detection_result.elements)} elements in {detection_result.processing_time_ms:.0f}ms")
        print(f"[ContextEngine] OCR found {len(ocr_result.text_regions)} text regions in {ocr_result.processing_time_ms:.0f}ms")
        print(f"[ContextEngine] Parallel processing took {parallel_time:.0f}ms")

        # Log sample OCR text
        if ocr_result.text_regions:
            sample_texts = [r.text for r in ocr_result.text_regions[:10]]
            print(f"[ContextEngine] Sample OCR texts: {sample_texts}")

        # Scale coordinates back to original image size
        elements = self._scale_elements_to_original(
            detection_result.elements,
            preprocessed.scale_factor
        )
        text_regions = self._scale_text_regions_to_original(
            ocr_result.text_regions,
            preprocessed.scale_factor
        )

        # Fuse text labels with UI elements
        if fuse_labels:
            elements = self._fuse_labels_with_elements(elements, text_regions)

            # Count elements with labels after fusion
            labeled_count = sum(1 for e in elements if e.label)
            print(f"[ContextEngine] After fusion: {labeled_count}/{len(elements)} elements have labels")

        total_time = (time.perf_counter() - start_time) * 1000

        return ScreenState(
            capture_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            image_size=preprocessed.original_size,
            elements=elements,
            text_regions=text_regions,
            processing_time_ms=total_time,
            metadata={
                "detection_time_ms": detection_result.processing_time_ms,
                "ocr_time_ms": ocr_result.processing_time_ms,
                "model_name": detection_result.model_name,
                "ocr_language": ocr_result.language,
                "resized": resize,
                "original_size": preprocessed.original_size,
                "processed_size": preprocessed.processed_size
            }
        )

    def analyze_from_bytes(
        self,
        image_bytes: bytes,
        resize: bool = True,
        fuse_labels: bool = True
    ) -> ScreenState:
        """
        Analyze from raw image bytes.

        Args:
            image_bytes: Raw image bytes
            resize: Whether to resize large images
            fuse_labels: Whether to associate text with UI elements

        Returns:
            Complete ScreenState
        """
        start_time = time.perf_counter()

        # Preprocess image
        preprocessed = self.preprocessor.preprocess_from_bytes(image_bytes, resize=resize)

        # Run detection and OCR in parallel for better performance
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            detection_future = executor.submit(self.detector.detect, preprocessed.image)
            ocr_future = executor.submit(self.ocr_engine.extract_text, preprocessed.image)

            detection_result = detection_future.result()
            ocr_result = ocr_future.result()

        # Scale coordinates back to original image size
        elements = self._scale_elements_to_original(
            detection_result.elements,
            preprocessed.scale_factor
        )
        text_regions = self._scale_text_regions_to_original(
            ocr_result.text_regions,
            preprocessed.scale_factor
        )

        # Fuse text labels with UI elements
        if fuse_labels:
            elements = self._fuse_labels_with_elements(elements, text_regions)

        total_time = (time.perf_counter() - start_time) * 1000

        return ScreenState(
            capture_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            image_size=preprocessed.original_size,
            elements=elements,
            text_regions=text_regions,
            processing_time_ms=total_time,
            metadata={
                "detection_time_ms": detection_result.processing_time_ms,
                "ocr_time_ms": ocr_result.processing_time_ms,
                "model_name": detection_result.model_name,
                "ocr_language": ocr_result.language
            }
        )

    def detect_ui_only(
        self,
        base64_image: str,
        resize: bool = True
    ) -> DetectionResult:
        """
        Run only UI element detection (no OCR).

        Args:
            base64_image: Base64 encoded image string
            resize: Whether to resize large images

        Returns:
            DetectionResult with UI elements
        """
        preprocessed = self.preprocessor.preprocess(base64_image, resize=resize)
        result = self.detector.detect(preprocessed.image)

        # Scale coordinates back to original
        scaled_elements = self._scale_elements_to_original(
            result.elements,
            preprocessed.scale_factor
        )

        return DetectionResult(
            elements=scaled_elements,
            processing_time_ms=result.processing_time_ms,
            model_name=result.model_name,
            image_size=preprocessed.original_size
        )

    def extract_text_only(
        self,
        base64_image: str,
        resize: bool = True
    ) -> OCRResult:
        """
        Run only OCR text extraction (no UI detection).

        Args:
            base64_image: Base64 encoded image string
            resize: Whether to resize large images

        Returns:
            OCRResult with text regions
        """
        preprocessed = self.preprocessor.preprocess(base64_image, resize=resize)
        result = self.ocr_engine.extract_text(preprocessed.image)

        # Scale coordinates back to original
        scaled_regions = self._scale_text_regions_to_original(
            result.text_regions,
            preprocessed.scale_factor
        )

        return OCRResult(
            text_regions=scaled_regions,
            processing_time_ms=result.processing_time_ms,
            language=result.language
        )

    def _scale_elements_to_original(
        self,
        elements: List[UIElement],
        scale_factor: Tuple[float, float]
    ) -> List[UIElement]:
        """Scale element coordinates back to original image size."""
        if scale_factor == (1.0, 1.0):
            return elements

        scaled = []
        for elem in elements:
            scaled_bbox = self.preprocessor.scale_bbox_to_original(
                elem.bbox, scale_factor
            )
            scaled.append(UIElement(
                element_id=elem.element_id,
                element_type=elem.element_type,
                bbox=scaled_bbox,
                confidence=elem.confidence,
                label=elem.label,
                metadata=elem.metadata
            ))
        return scaled

    def _scale_text_regions_to_original(
        self,
        regions: List[TextRegion],
        scale_factor: Tuple[float, float]
    ) -> List[TextRegion]:
        """Scale text region coordinates back to original image size."""
        if scale_factor == (1.0, 1.0):
            return regions

        scaled = []
        for region in regions:
            scaled_bbox = self.preprocessor.scale_bbox_to_original(
                region.bbox, scale_factor
            )
            scaled.append(TextRegion(
                text=region.text,
                bbox=scaled_bbox,
                confidence=region.confidence,
                metadata=region.metadata
            ))
        return scaled

    def _fuse_labels_with_elements(
        self,
        elements: List[UIElement],
        text_regions: List[TextRegion]
    ) -> List[UIElement]:
        """
        Associate text labels with UI elements based on spatial proximity.

        Scoring:
        - Text inside element: score 1.0
        - Text overlapping element: score based on IoU
        - Text nearby element: score based on distance (up to 0.7)

        Args:
            elements: List of detected UI elements
            text_regions: List of OCR text regions

        Returns:
            Elements with labels assigned
        """
        labeled_elements = []

        for elem in elements:
            best_label = None
            best_score = 0.0

            for region in text_regions:
                score = self._calculate_association_score(elem.bbox, region.bbox)

                if score > best_score:
                    best_score = score
                    best_label = region.text

            # Only assign label if score is above threshold (lowered from 0.3 to 0.1 for better coverage)
            if best_score >= 0.1:
                labeled_elements.append(UIElement(
                    element_id=elem.element_id,
                    element_type=elem.element_type,
                    bbox=elem.bbox,
                    confidence=elem.confidence,
                    label=best_label,
                    metadata={
                        **elem.metadata,
                        "label_score": best_score
                    }
                ))
            else:
                labeled_elements.append(elem)

        return labeled_elements

    def _calculate_association_score(
        self,
        element_bbox: BoundingBox,
        text_bbox: BoundingBox
    ) -> float:
        """
        Calculate association score between element and text.

        Returns:
            Score from 0.0 to 1.0
        """
        # Check if text center is inside element
        text_center = text_bbox.center
        if element_bbox.contains_point(text_center[0], text_center[1]):
            return 1.0

        # Check overlap using IoU
        if element_bbox.overlaps(text_bbox):
            iou = element_bbox.iou(text_bbox)
            return 0.8 + (iou * 0.2)  # 0.8 to 1.0 based on IoU

        # Calculate distance-based score for nearby text
        elem_center = element_bbox.center
        text_center = text_bbox.center

        distance = ((elem_center[0] - text_center[0]) ** 2 +
                    (elem_center[1] - text_center[1]) ** 2) ** 0.5

        # Use element size as reference for "nearby" threshold
        reference_size = max(element_bbox.width, element_bbox.height)
        max_distance = reference_size * 4  # Consider text within 4x element size (increased from 2x)

        if distance < max_distance:
            # Linear falloff from 0.7 to 0.0 based on distance
            return 0.7 * (1 - distance / max_distance)

        # Even for far away text, return small score if within 200 pixels
        if distance < 200:
            return 0.1

        return 0.0

    def get_health_status(self) -> dict:
        """
        Get health status of all CV components.

        Returns:
            Dictionary with component health info
        """
        # Detect which type of detector is being used
        detector_info = self.detector.get_model_info()
        detector_type = detector_info.get("detector", "unknown")
        if hasattr(self.detector, 'icon_detect_path'):
            detector_type = "omniparser"
        elif hasattr(self.detector, 'model_path'):
            detector_type = "yolo"

        return {
            "detector": {
                "type": detector_type,
                **detector_info
            },
            "ocr_engine": self.ocr_engine.get_engine_info(),
            "preprocessor": {
                "max_size_mb": self.preprocessor.max_size_bytes / (1024 * 1024),
                "supported_formats": self.preprocessor.supported_formats
            }
        }


def create_context_engine_from_settings(settings) -> ContextEngine:
    """
    Factory function to create context engine from app settings.

    Uses OmniParser by default if available, falls back to YOLO.

    Args:
        settings: Application settings object

    Returns:
        Configured ContextEngine
    """
    import os

    preprocessor = ImagePreprocessor(
        max_size_mb=settings.CV_MAX_IMAGE_SIZE_MB,
        supported_formats=settings.CV_SUPPORTED_FORMATS,
        default_resize_width=settings.CV_DEFAULT_RESIZE_WIDTH,
        default_resize_height=settings.CV_DEFAULT_RESIZE_HEIGHT
    )

    # Choose detector based on settings and availability
    detector = None
    if settings.CV_DETECTION_BACKEND == "omniparser":
        icon_detect_path = settings.OMNIPARSER_ICON_DETECT_PATH
        if os.path.exists(icon_detect_path):
            from .omniparser_detector import OmniParserDetector
            use_openvino = getattr(settings, 'OMNIPARSER_USE_OPENVINO', True)
            detector = OmniParserDetector(
                icon_detect_path=settings.OMNIPARSER_ICON_DETECT_PATH,
                icon_caption_path=settings.OMNIPARSER_ICON_CAPTION_PATH,
                confidence_threshold=settings.OMNIPARSER_CONFIDENCE_THRESHOLD,
                iou_threshold=settings.OMNIPARSER_IOU_THRESHOLD,
                device="cuda" if settings.OCR_USE_GPU else "cpu",
                enable_captioning=settings.OMNIPARSER_ENABLE_CAPTIONING,
                use_openvino=use_openvino
            )
            openvino_status = "with OpenVINO" if use_openvino else "without OpenVINO"
            print(f"Using OmniParser detector from {icon_detect_path} ({openvino_status})")
        else:
            print(f"OmniParser model not found at {icon_detect_path}, falling back to YOLO")

    # Fall back to YOLO if OmniParser not configured or not available
    if detector is None:
        detector = YOLODetector(
            model_path=settings.YOLO_MODEL_PATH,
            confidence_threshold=settings.YOLO_CONFIDENCE_THRESHOLD,
            iou_threshold=settings.YOLO_IOU_THRESHOLD,
            device="cuda" if settings.OCR_USE_GPU else "cpu"
        )
        print(f"Using YOLO detector: {settings.YOLO_MODEL_PATH}")

    # Select OCR engine based on settings
    ocr_backend = getattr(settings, 'OCR_BACKEND', 'easyocr')
    if ocr_backend == "paddleocr":
        from .paddle_ocr_engine import PaddleOCREngine
        ocr_engine = PaddleOCREngine(
            language=settings.OCR_LANGUAGE,
            use_gpu=settings.OCR_USE_GPU,
            confidence_threshold=settings.OCR_CONFIDENCE_THRESHOLD,
            use_angle_cls=getattr(settings, 'PADDLEOCR_USE_ANGLE_CLS', False)
        )
        print(f"Using PaddleOCR engine (language: {settings.OCR_LANGUAGE})")
    else:
        ocr_engine = OCREngine(
            language=settings.OCR_LANGUAGE,
            use_gpu=settings.OCR_USE_GPU,
            confidence_threshold=settings.OCR_CONFIDENCE_THRESHOLD
        )
        print(f"Using EasyOCR engine (language: {settings.OCR_LANGUAGE})")

    return ContextEngine(
        preprocessor=preprocessor,
        detector=detector,
        ocr_engine=ocr_engine
    )
