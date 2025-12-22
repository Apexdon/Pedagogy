"""
YOLO v11 UI Element Detector

Uses ultralytics YOLO v11 for detecting UI elements in screenshots.
Implements lazy model loading with global cache.
"""

import time
import uuid
from typing import Dict, List, Optional, Tuple

import numpy as np

from .data_classes import BoundingBox, UIElement, DetectionResult


# Global model cache for lazy loading
_yolo_model_cache: Dict[str, "YOLO"] = {}


def _get_yolo_model(model_path: str) -> "YOLO":
    """
    Get or load YOLO model with caching.

    Models are loaded on first use and cached globally.
    This follows the same pattern as the embedding model in rag_system.

    Args:
        model_path: Path to YOLO model file (e.g., "yolo11n.pt")

    Returns:
        Loaded YOLO model
    """
    global _yolo_model_cache

    if model_path not in _yolo_model_cache:
        from ultralytics import YOLO
        _yolo_model_cache[model_path] = YOLO(model_path)

    return _yolo_model_cache[model_path]


# UI element class mapping for YOLO COCO classes
# Default YOLO v11 uses COCO classes - this maps relevant ones to UI types
# For production, train a custom model on UI element datasets
COCO_TO_UI_MAPPING = {
    # These are placeholder mappings - real UI detection needs custom training
    "cell phone": "mobile_screen",
    "laptop": "screen",
    "tv": "screen",
    "keyboard": "input_device",
    "mouse": "input_device",
    "remote": "control",
    "book": "document",
}


class YOLODetector:
    """
    YOLO v11 based UI element detector.

    Uses ultralytics package which supports YOLO v11 models.
    Model is lazily loaded on first detection.
    """

    def __init__(
        self,
        model_path: str = "yolo11n.pt",
        confidence_threshold: float = 0.5,
        iou_threshold: float = 0.45,
        device: Optional[str] = None
    ):
        """
        Initialize the YOLO detector.

        Args:
            model_path: Path to YOLO model (auto-downloads if not present)
            confidence_threshold: Minimum confidence for detections
            iou_threshold: IoU threshold for NMS
            device: Device to run on ("cpu", "cuda", etc.). Auto-detected if None.
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.device = device
        self._model = None

    @property
    def model(self):
        """Lazy-load the YOLO model."""
        if self._model is None:
            self._model = _get_yolo_model(self.model_path)
        return self._model

    def detect(
        self,
        image: np.ndarray,
        classes: Optional[List[int]] = None
    ) -> DetectionResult:
        """
        Detect UI elements in an image.

        Args:
            image: BGR numpy array (OpenCV format)
            classes: Optional list of class IDs to detect

        Returns:
            DetectionResult with detected UIElements
        """
        start_time = time.perf_counter()

        # Run inference
        results = self.model.predict(
            image,
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            device=self.device,
            classes=classes,
            verbose=False
        )

        # Process results
        elements: List[UIElement] = []

        if results and len(results) > 0:
            result = results[0]  # First (and usually only) result

            if result.boxes is not None:
                boxes = result.boxes

                for i in range(len(boxes)):
                    # Get box coordinates (x1, y1, x2, y2)
                    box = boxes.xyxy[i].cpu().numpy()
                    confidence = float(boxes.conf[i].cpu().numpy())
                    class_id = int(boxes.cls[i].cpu().numpy())

                    # Get class name
                    class_name = result.names.get(class_id, f"class_{class_id}")

                    # Map to UI element type
                    element_type = COCO_TO_UI_MAPPING.get(class_name, class_name)

                    # Create bounding box
                    bbox = BoundingBox(
                        x1=int(box[0]),
                        y1=int(box[1]),
                        x2=int(box[2]),
                        y2=int(box[3])
                    )

                    # Create UI element
                    element = UIElement(
                        element_id=str(uuid.uuid4()),
                        element_type=element_type,
                        bbox=bbox,
                        confidence=confidence,
                        label=None,  # Will be filled by OCR fusion
                        metadata={
                            "class_id": class_id,
                            "class_name": class_name
                        }
                    )
                    elements.append(element)

        processing_time = (time.perf_counter() - start_time) * 1000  # Convert to ms

        height, width = image.shape[:2]

        return DetectionResult(
            elements=elements,
            processing_time_ms=processing_time,
            model_name=self.model_path,
            image_size=(width, height)
        )

    def detect_with_ui_classes(
        self,
        image: np.ndarray,
        ui_class_ids: Optional[List[int]] = None
    ) -> DetectionResult:
        """
        Detect with focus on UI-relevant classes.

        This is a convenience method that filters to common UI-related
        COCO classes. For real UI detection, use a custom-trained model.

        Args:
            image: BGR numpy array
            ui_class_ids: Specific class IDs to detect

        Returns:
            DetectionResult
        """
        # Common COCO classes that might be UI-related
        # 63: laptop, 62: tv, 67: cell phone, 66: keyboard, 64: mouse
        default_ui_classes = [62, 63, 64, 66, 67]
        classes = ui_class_ids or default_ui_classes

        return self.detect(image, classes=classes)

    def get_model_info(self) -> Dict:
        """
        Get information about the loaded model.

        Returns:
            Dictionary with model details
        """
        return {
            "model_path": self.model_path,
            "confidence_threshold": self.confidence_threshold,
            "iou_threshold": self.iou_threshold,
            "device": self.device or "auto",
            "loaded": self._model is not None
        }

    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._model is not None


def create_detector_from_settings(settings) -> YOLODetector:
    """
    Factory function to create detector from app settings.

    Args:
        settings: Application settings object

    Returns:
        Configured YOLODetector
    """
    return YOLODetector(
        model_path=settings.YOLO_MODEL_PATH,
        confidence_threshold=settings.YOLO_CONFIDENCE_THRESHOLD,
        iou_threshold=settings.YOLO_IOU_THRESHOLD,
        device="cuda" if settings.OCR_USE_GPU else "cpu"
    )
