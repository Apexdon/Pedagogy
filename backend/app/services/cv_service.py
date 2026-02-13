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
    ImageSizeSchema,
    DiagnosticResponse,
    OCRDiagnosticResult,
    DetectionDiagnosticResult,
    TimingStep
)
import time
import uuid
from datetime import datetime


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

    async def run_diagnostic(
        self,
        image_base64: str,
        resize: bool = True,
        run_ocr: bool = True,
        run_detection: bool = True
    ) -> DiagnosticResponse:
        """
        Run diagnostic analysis with detailed timing breakdown.

        Args:
            image_base64: Base64 encoded image
            resize: Whether to resize large images
            run_ocr: Whether to run OCR text extraction
            run_detection: Whether to run UI element detection

        Returns:
            DiagnosticResponse with detailed timing for each step
        """
        analysis_start = time.perf_counter()
        analysis_id = str(uuid.uuid4())

        # Preprocessing
        preprocess_start = time.perf_counter()
        preprocessed = self.context_engine.preprocessor.preprocess(
            image_base64,
            resize=resize
        )
        preprocess_time = (time.perf_counter() - preprocess_start) * 1000

        # Apply browser chrome cropping
        image = preprocessed.image
        crop_start = time.perf_counter()
        cropped_image, crop_offset = self.context_engine._crop_browser_chrome(image)
        crop_time = (time.perf_counter() - crop_start) * 1000

        ocr_result = None
        detection_result = None

        # Run OCR with detailed timing
        if run_ocr:
            ocr_result = self._run_ocr_diagnostic(cropped_image, analysis_start)

        # Run Detection with detailed timing
        if run_detection:
            detection_result = self._run_detection_diagnostic(cropped_image, analysis_start)

        total_time = (time.perf_counter() - analysis_start) * 1000

        # Check if image was resized
        was_resized = preprocessed.original_size != preprocessed.processed_size

        # Build summary
        summary = {
            "preprocessing_ms": preprocess_time,
            "crop_ms": crop_time,
            "crop_offset_y": crop_offset,
            "image_resized": was_resized,
            "original_size": preprocessed.original_size,
            "processed_size": (cropped_image.shape[1], cropped_image.shape[0]),
        }

        if ocr_result:
            summary["ocr_total_ms"] = ocr_result.total_time_ms
            summary["ocr_regions"] = ocr_result.text_region_count

        if detection_result:
            summary["detection_total_ms"] = detection_result.total_time_ms
            summary["detection_elements"] = detection_result.element_count

        return DiagnosticResponse(
            analysis_id=analysis_id,
            timestamp=datetime.utcnow(),
            image_size=ImageSizeSchema(
                width=preprocessed.original_size[0],
                height=preprocessed.original_size[1]
            ),
            total_time_ms=total_time,
            preprocessing_time_ms=preprocess_time + crop_time,
            ocr_result=ocr_result,
            detection_result=detection_result,
            summary=summary
        )

    def _run_ocr_diagnostic(self, image, analysis_start: float) -> OCRDiagnosticResult:
        """Run OCR with detailed timing breakdown."""
        timing_steps = []

        # Get the OCR engine
        ocr_engine = self.context_engine.ocr_engine

        # Start OCR
        ocr_start = time.perf_counter()
        ocr_start_ms = (ocr_start - analysis_start) * 1000

        # Call OCR with detailed timing if available (OpenVINO has 'ocr' property)
        result = None
        elapse = None

        if hasattr(ocr_engine, 'ocr'):
            # OpenVINO OCR engine - returns (result, elapse) tuple
            result, elapse = ocr_engine.ocr(image, use_cls=False)
        else:
            # EasyOCR or other engines - use extract_text method
            ocr_result = ocr_engine.extract_text(image)
            # Convert to RapidOCR format for consistent processing
            result = []
            for region in ocr_result.text_regions:
                bbox_points = [
                    [region.bbox.x1, region.bbox.y1],
                    [region.bbox.x2, region.bbox.y1],
                    [region.bbox.x2, region.bbox.y2],
                    [region.bbox.x1, region.bbox.y2]
                ]
                result.append((bbox_points, region.text, region.confidence))

        ocr_end = time.perf_counter()
        ocr_end_ms = (ocr_end - analysis_start) * 1000
        total_time = (ocr_end - ocr_start) * 1000

        # Parse RapidOCR elapse timing (det_time, cls_time, rec_time)
        if elapse:
            # RapidOCR returns timing as: det, cls, rec (in seconds)
            det_time_s = elapse.get('det', 0) if isinstance(elapse, dict) else (elapse[0] if len(elapse) > 0 else 0)
            cls_time_s = elapse.get('cls', 0) if isinstance(elapse, dict) else (elapse[1] if len(elapse) > 1 else 0)
            rec_time_s = elapse.get('rec', 0) if isinstance(elapse, dict) else (elapse[2] if len(elapse) > 2 else 0)

            det_time_ms = det_time_s * 1000 if det_time_s else 0
            cls_time_ms = cls_time_s * 1000 if cls_time_s else 0
            rec_time_ms = rec_time_s * 1000 if rec_time_s else 0

            timing_steps.append(TimingStep(
                name="Text Detection (DBNet)",
                start_ms=ocr_start_ms,
                end_ms=ocr_start_ms + det_time_ms,
                duration_ms=det_time_ms,
                details={"model": "DBNet", "description": "Detects text regions in image"}
            ))

            if cls_time_ms > 0:
                timing_steps.append(TimingStep(
                    name="Text Direction Classification",
                    start_ms=ocr_start_ms + det_time_ms,
                    end_ms=ocr_start_ms + det_time_ms + cls_time_ms,
                    duration_ms=cls_time_ms,
                    details={"model": "Classifier", "description": "Classifies text direction (skipped if use_cls=False)"}
                ))

            timing_steps.append(TimingStep(
                name="Text Recognition (CRNN)",
                start_ms=ocr_start_ms + det_time_ms + cls_time_ms,
                end_ms=ocr_end_ms,
                duration_ms=rec_time_ms,
                details={
                    "model": "CRNN",
                    "description": "Recognizes text in each detected region",
                    "regions_processed": len(result) if result else 0
                }
            ))
        else:
            timing_steps.append(TimingStep(
                name="OCR Processing",
                start_ms=ocr_start_ms,
                end_ms=ocr_end_ms,
                duration_ms=total_time,
                details={"description": "Combined OCR processing"}
            ))

        # Process results
        text_regions = []
        if result:
            for item in result:
                bbox_points, text, confidence = item
                if not text or not text.strip():
                    continue
                if float(confidence) < ocr_engine.confidence_threshold:
                    continue

                xs = [p[0] for p in bbox_points]
                ys = [p[1] for p in bbox_points]

                text_regions.append(TextRegionSchema(
                    text=text.strip(),
                    bbox=BoundingBoxSchema(
                        x1=int(min(xs)),
                        y1=int(min(ys)),
                        x2=int(max(xs)),
                        y2=int(max(ys))
                    ),
                    confidence=float(confidence),
                    metadata={"engine": "rapidocr_openvino"}
                ))

        return OCRDiagnosticResult(
            total_time_ms=total_time,
            text_region_count=len(text_regions),
            timing_steps=timing_steps,
            text_regions=text_regions,
            engine_info=ocr_engine.get_engine_info()
        )

    def _run_detection_diagnostic(self, image, analysis_start: float) -> DetectionDiagnosticResult:
        """Run UI detection with detailed timing breakdown."""
        timing_steps = []

        # Get the detector
        detector = self.context_engine.detector

        # Start detection
        detect_start = time.perf_counter()
        detect_start_ms = (detect_start - analysis_start) * 1000

        # Run detection
        result = detector.detect(image, generate_captions=False)

        detect_end = time.perf_counter()
        detect_end_ms = (detect_end - analysis_start) * 1000
        total_time = (detect_end - detect_start) * 1000

        # Add timing step
        timing_steps.append(TimingStep(
            name="YOLO Inference",
            start_ms=detect_start_ms,
            end_ms=detect_end_ms,
            duration_ms=total_time,
            details={
                "model": result.model_name,
                "elements_detected": len(result.elements),
                "description": "UI element detection using YOLO/OmniParser"
            }
        ))

        # Convert elements
        elements = [
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
        ]

        return DetectionDiagnosticResult(
            total_time_ms=total_time,
            element_count=len(elements),
            timing_steps=timing_steps,
            elements=elements,
            model_info=detector.get_model_info()
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
