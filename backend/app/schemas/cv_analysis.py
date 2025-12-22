"""
CV Analysis Pydantic Schemas

Request and response models for CV pipeline API endpoints.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


# =============================================
# Nested Models
# =============================================

class BoundingBoxSchema(BaseModel):
    """Bounding box coordinates."""
    x1: int = Field(..., description="Left x coordinate")
    y1: int = Field(..., description="Top y coordinate")
    x2: int = Field(..., description="Right x coordinate")
    y2: int = Field(..., description="Bottom y coordinate")


class ImageSizeSchema(BaseModel):
    """Image dimensions."""
    width: int = Field(..., description="Image width in pixels")
    height: int = Field(..., description="Image height in pixels")


class UIElementSchema(BaseModel):
    """Detected UI element."""
    element_id: str = Field(..., description="Unique element identifier")
    type: str = Field(..., description="Element type (button, input, etc.)")
    label: Optional[str] = Field(None, description="Associated text label")
    bbox: BoundingBoxSchema = Field(..., description="Bounding box coordinates")
    confidence: float = Field(..., ge=0, le=1, description="Detection confidence")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class TextRegionSchema(BaseModel):
    """Extracted text region."""
    text: str = Field(..., description="Extracted text content")
    bbox: BoundingBoxSchema = Field(..., description="Bounding box coordinates")
    confidence: float = Field(..., ge=0, le=1, description="OCR confidence")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


# =============================================
# Request Schemas
# =============================================

class AnalyzeScreenRequest(BaseModel):
    """Request for full screen analysis."""
    image: str = Field(
        ...,
        description="Base64 encoded image (with or without data URI prefix)"
    )
    resize: bool = Field(
        default=True,
        description="Whether to resize large images for faster processing"
    )
    fuse_labels: bool = Field(
        default=True,
        description="Whether to associate OCR text with detected UI elements"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "resize": True,
                "fuse_labels": True
            }
        }


class DetectUIRequest(BaseModel):
    """Request for UI element detection only."""
    image: str = Field(
        ...,
        description="Base64 encoded image"
    )
    resize: bool = Field(
        default=True,
        description="Whether to resize large images"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "image": "data:image/png;base64,...",
                "resize": True
            }
        }


class ExtractTextRequest(BaseModel):
    """Request for text extraction only."""
    image: str = Field(
        ...,
        description="Base64 encoded image"
    )
    resize: bool = Field(
        default=True,
        description="Whether to resize large images"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "image": "data:image/png;base64,...",
                "resize": True
            }
        }


# =============================================
# Response Schemas
# =============================================

class ScreenStateResponse(BaseModel):
    """Full screen analysis response."""
    capture_id: str = Field(..., description="Unique capture identifier")
    timestamp: datetime = Field(..., description="Analysis timestamp")
    image_size: ImageSizeSchema = Field(..., description="Original image dimensions")
    elements: List[UIElementSchema] = Field(
        default_factory=list,
        description="Detected UI elements"
    )
    text_regions: List[TextRegionSchema] = Field(
        default_factory=list,
        description="Extracted text regions"
    )
    processing_time_ms: float = Field(..., description="Total processing time in milliseconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Processing metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "capture_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2024-12-18T10:30:00Z",
                "image_size": {"width": 1920, "height": 1080},
                "elements": [
                    {
                        "element_id": "elem-001",
                        "type": "button",
                        "label": "Submit",
                        "bbox": {"x1": 100, "y1": 200, "x2": 200, "y2": 250},
                        "confidence": 0.95,
                        "metadata": {}
                    }
                ],
                "text_regions": [
                    {
                        "text": "Enter your email",
                        "bbox": {"x1": 50, "y1": 100, "x2": 200, "y2": 130},
                        "confidence": 0.98,
                        "metadata": {}
                    }
                ],
                "processing_time_ms": 245.5,
                "metadata": {
                    "detection_time_ms": 120.2,
                    "ocr_time_ms": 125.3
                }
            }
        }


class DetectUIResponse(BaseModel):
    """UI detection only response."""
    elements: List[UIElementSchema] = Field(
        default_factory=list,
        description="Detected UI elements"
    )
    element_count: int = Field(..., description="Number of detected elements")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    model_name: str = Field(..., description="YOLO model used")
    image_size: ImageSizeSchema = Field(..., description="Image dimensions")


class ExtractTextResponse(BaseModel):
    """Text extraction only response."""
    text_regions: List[TextRegionSchema] = Field(
        default_factory=list,
        description="Extracted text regions"
    )
    region_count: int = Field(..., description="Number of text regions")
    full_text: str = Field(..., description="All extracted text concatenated")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    language: str = Field(..., description="OCR language used")


class CVHealthResponse(BaseModel):
    """CV pipeline health status response."""
    status: str = Field(..., description="Overall status (healthy, degraded, unhealthy)")
    detector: Dict[str, Any] = Field(..., description="YOLO detector status")
    ocr_engine: Dict[str, Any] = Field(..., description="OCR engine status")
    preprocessor: Dict[str, Any] = Field(..., description="Preprocessor configuration")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "detector": {
                    "type": "yolo",
                    "model_path": "yolo11n.pt",
                    "loaded": True
                },
                "ocr_engine": {
                    "engine": "easyocr",
                    "language": "en",
                    "loaded": True
                },
                "preprocessor": {
                    "max_size_mb": 10,
                    "supported_formats": ["png", "jpg", "jpeg", "bmp", "webp"]
                }
            }
        }
