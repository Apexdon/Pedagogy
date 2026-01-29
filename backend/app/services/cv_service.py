"""
CV Service

Service layer for CV pipeline operations.
Coordinates CV analysis and provides clean API for routes.
"""

from typing import Dict, Any

from app.config import settings
from cv_pipeline import (
    ContextEngine,
    create_context_engine_from_settings,
    ScreenState,
    DetectionResult,
    OCRResult
)
from app.schemas.cv_analysis import (
    ScreenStateResponse,
    DetectUIResponse,
    ExtractTextResponse,
    CVHealthResponse,
    UIElementSchema,
    TextRegionSchema,
    BoundingBoxSchema,
    ImageSizeSchema
)


class CVService:
    """
    Service for CV pipeline operations.

    Wraps the CV pipeline context engine and provides
    methods for screen analysis, UI detection, and text extraction.
    """

    def __init__(self):
        """Initialize the CV service with default settings."""
        self._context_engine: ContextEngine = None

    @property
    def context_engine(self) -> ContextEngine:
        """Lazy-load the context engine."""
        if self._context_engine is None:
            self._context_engine = create_context_engine_from_settings(settings)
        return self._context_engine

    async def analyze_screen(
        self,
        image_base64: str,
        resize: bool = True,
        fuse_labels: bool = True
    ) -> ScreenStateResponse:
        """
        Perform full screen analysis (detection + OCR + fusion).

        Args:
            image_base64: Base64 encoded image
            resize: Whether to resize large images
            fuse_labels: Whether to associate text with UI elements

        Returns:
            ScreenStateResponse with complete analysis
        """
        # Run analysis (synchronous, but fast enough for API)
        screen_state = self.context_engine.analyze(
            image_base64,
            resize=resize,
            fuse_labels=fuse_labels
        )

        return self._screen_state_to_response(screen_state)

    async def detect_ui_elements(
        self,
        image_base64: str,
        resize: bool = True
    ) -> DetectUIResponse:
        """
        Detect UI elements only (no OCR).

        Args:
            image_base64: Base64 encoded image
            resize: Whether to resize large images

        Returns:
            DetectUIResponse with detected elements
        """
        result = self.context_engine.detect_ui_only(image_base64, resize=resize)

        return DetectUIResponse(
            elements=[
                UIElementSchema(
                    element_id=elem.element_id,
                    type=elem.element_type,
                    label=elem.label,
                    bbox=BoundingBoxSchema(
                        x1=elem.bbox.x1,
                        y1=elem.bbox.y1,
                        x2=elem.bbox.x2,
                        y2=elem.bbox.y2
                    ),
                    confidence=elem.confidence,
                    metadata=elem.metadata
                )
                for elem in result.elements
            ],
            element_count=len(result.elements),
            processing_time_ms=result.processing_time_ms,
            model_name=result.model_name,
            image_size=ImageSizeSchema(
                width=result.image_size[0],
                height=result.image_size[1]
            )
        )

    async def extract_text(
        self,
        image_base64: str,
        resize: bool = True
    ) -> ExtractTextResponse:
        """
        Extract text only (no UI detection).

        Args:
            image_base64: Base64 encoded image
            resize: Whether to resize large images

        Returns:
            ExtractTextResponse with extracted text
        """
        result = self.context_engine.extract_text_only(image_base64, resize=resize)

        return ExtractTextResponse(
            text_regions=[
                TextRegionSchema(
                    text=region.text,
                    bbox=BoundingBoxSchema(
                        x1=region.bbox.x1,
                        y1=region.bbox.y1,
                        x2=region.bbox.x2,
                        y2=region.bbox.y2
                    ),
                    confidence=region.confidence,
                    metadata=region.metadata
                )
                for region in result.text_regions
            ],
            region_count=len(result.text_regions),
            full_text=result.full_text,
            processing_time_ms=result.processing_time_ms,
            language=result.language
        )

    async def get_health_status(self) -> CVHealthResponse:
        """
        Get CV pipeline health status.

        Returns:
            CVHealthResponse with component status
        """
        health = self.context_engine.get_health_status()

        # Determine overall status
        detector_loaded = health.get("detector", {}).get("loaded", False)
        ocr_loaded = health.get("ocr_engine", {}).get("loaded", False)

        if detector_loaded and ocr_loaded:
            status = "healthy"
        elif detector_loaded or ocr_loaded:
            status = "degraded"
        else:
            status = "ready"  # Not unhealthy, just not loaded yet (lazy loading)

        return CVHealthResponse(
            status=status,
            detector=health.get("detector", {}),
            ocr_engine=health.get("ocr_engine", {}),
            preprocessor=health.get("preprocessor", {})
        )

    def _screen_state_to_response(self, state: ScreenState) -> ScreenStateResponse:
        """Convert ScreenState dataclass to Pydantic response."""
        return ScreenStateResponse(
            capture_id=state.capture_id,
            timestamp=state.timestamp,
            image_size=ImageSizeSchema(
                width=state.image_size[0],
                height=state.image_size[1]
            ),
            elements=[
                UIElementSchema(
                    element_id=elem.element_id,
                    type=elem.element_type,
                    label=elem.label,
                    bbox=BoundingBoxSchema(
                        x1=elem.bbox.x1,
                        y1=elem.bbox.y1,
                        x2=elem.bbox.x2,
                        y2=elem.bbox.y2
                    ),
                    confidence=elem.confidence,
                    metadata=elem.metadata
                )
                for elem in state.elements
            ],
            text_regions=[
                TextRegionSchema(
                    text=region.text,
                    bbox=BoundingBoxSchema(
                        x1=region.bbox.x1,
                        y1=region.bbox.y1,
                        x2=region.bbox.x2,
                        y2=region.bbox.y2
                    ),
                    confidence=region.confidence,
                    metadata=region.metadata
                )
                for region in state.text_regions
            ],
            processing_time_ms=state.processing_time_ms,
            metadata=state.metadata
        )


# Global service instance
_cv_service: CVService = None


def get_cv_service() -> CVService:
    """
    Get or create CV service instance.

    Returns:
        CVService instance
    """
    global _cv_service
    if _cv_service is None:
        _cv_service = CVService()
    return _cv_service


def reset_cv_service() -> None:
    """
    Reset the CV service instance, forcing reinitialization.

    Call this when settings change and you need the CV service
    to pick up new configuration (e.g., switching OCR backends).
    """
    global _cv_service
    if _cv_service is not None:
        print("[CVService] Resetting CV service instance...")
        _cv_service._context_engine = None
        _cv_service = None
    print("[CVService] CV service will be reinitialized on next use")
