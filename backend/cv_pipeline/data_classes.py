"""
CV Pipeline Data Classes

Internal data structures for CV pipeline processing.
Uses dataclasses for internal representation (Pydantic is used only at API layer).
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import uuid


@dataclass
class BoundingBox:
    """Represents a bounding box with coordinates."""
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def center(self) -> Tuple[int, int]:
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

    @property
    def area(self) -> int:
        return self.width * self.height

    def to_dict(self) -> Dict[str, int]:
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}

    def contains_point(self, x: int, y: int) -> bool:
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2

    def overlaps(self, other: "BoundingBox") -> bool:
        return not (self.x2 < other.x1 or self.x1 > other.x2 or
                    self.y2 < other.y1 or self.y1 > other.y2)

    def iou(self, other: "BoundingBox") -> float:
        """Calculate Intersection over Union."""
        xi1 = max(self.x1, other.x1)
        yi1 = max(self.y1, other.y1)
        xi2 = min(self.x2, other.x2)
        yi2 = min(self.y2, other.y2)

        inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
        union_area = self.area + other.area - inter_area

        return inter_area / union_area if union_area > 0 else 0.0


@dataclass
class UIElement:
    """Detected UI element (button, input, dropdown, etc.)."""
    element_id: str
    element_type: str  # button, input, dropdown, checkbox, link, icon, menu, etc.
    bbox: BoundingBox
    confidence: float
    label: Optional[str] = None  # Associated text label (from OCR fusion)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_id": self.element_id,
            "type": self.element_type,
            "label": self.label,
            "bbox": self.bbox.to_dict(),
            "confidence": round(self.confidence, 4),
            "metadata": self.metadata
        }


@dataclass
class TextRegion:
    """Extracted text region from OCR."""
    text: str
    bbox: BoundingBox
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "bbox": self.bbox.to_dict(),
            "confidence": round(self.confidence, 4),
            "metadata": self.metadata
        }


@dataclass
class DetectionResult:
    """Result from YOLO UI element detection."""
    elements: List[UIElement]
    processing_time_ms: float
    model_name: str
    image_size: Tuple[int, int]  # (width, height)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "elements": [e.to_dict() for e in self.elements],
            "element_count": len(self.elements),
            "processing_time_ms": round(self.processing_time_ms, 2),
            "model_name": self.model_name,
            "image_size": {"width": self.image_size[0], "height": self.image_size[1]}
        }


@dataclass
class OCRResult:
    """Result from EasyOCR text extraction."""
    text_regions: List[TextRegion]
    processing_time_ms: float
    language: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text_regions": [t.to_dict() for t in self.text_regions],
            "region_count": len(self.text_regions),
            "processing_time_ms": round(self.processing_time_ms, 2),
            "language": self.language
        }

    @property
    def full_text(self) -> str:
        """Get all extracted text concatenated."""
        return " ".join(t.text for t in self.text_regions)


@dataclass
class ScreenState:
    """Combined screen state from UI detection + OCR."""
    capture_id: str
    timestamp: datetime
    image_size: Tuple[int, int]  # (width, height)
    elements: List[UIElement]
    text_regions: List[TextRegion]
    processing_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def create() -> "ScreenState":
        """Factory method to create new ScreenState with generated ID."""
        return ScreenState(
            capture_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            image_size=(0, 0),
            elements=[],
            text_regions=[],
            processing_time_ms=0.0
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capture_id": self.capture_id,
            "timestamp": self.timestamp.isoformat(),
            "image_size": {"width": self.image_size[0], "height": self.image_size[1]},
            "elements": [e.to_dict() for e in self.elements],
            "text_regions": [t.to_dict() for t in self.text_regions],
            "processing_time_ms": round(self.processing_time_ms, 2),
            "metadata": self.metadata
        }
