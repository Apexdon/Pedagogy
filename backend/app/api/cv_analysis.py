"""
CV Analysis API Routes

Endpoints for screen capture analysis, UI detection, and text extraction.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Annotated

from app.services.cv_service import CVService, get_cv_service
from app.schemas.cv_analysis import (
    AnalyzeScreenRequest,
    DetectUIRequest,
    ExtractTextRequest,
    ScreenStateResponse,
    DetectUIResponse,
    ExtractTextResponse,
    CVHealthResponse
)

router = APIRouter(prefix="/capture", tags=["Computer Vision"])


@router.post(
    "/analyze",
    response_model=ScreenStateResponse,
    summary="Analyze screen capture",
    description="Perform full screen analysis including UI element detection and text extraction"
)
async def analyze_screen(
    request: AnalyzeScreenRequest,
    cv_service: Annotated[CVService, Depends(get_cv_service)]
) -> ScreenStateResponse:
    """
    Analyze a screen capture to detect UI elements and extract text.

    This endpoint performs:
    1. Image preprocessing (decoding, validation, optional resizing)
    2. YOLO v11 UI element detection
    3. EasyOCR text extraction
    4. Label fusion (associating text with UI elements)

    Returns a complete screen state representation.
    """
    try:
        return await cv_service.analyze_screen(
            image_base64=request.image,
            resize=request.resize,
            fuse_labels=request.fuse_labels
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


@router.post(
    "/detect-ui",
    response_model=DetectUIResponse,
    summary="Detect UI elements",
    description="Detect UI elements in a screen capture using YOLO v11"
)
async def detect_ui_elements(
    request: DetectUIRequest,
    cv_service: Annotated[CVService, Depends(get_cv_service)]
) -> DetectUIResponse:
    """
    Detect UI elements in a screen capture.

    Uses YOLO v11 for fast and accurate element detection.
    Returns bounding boxes, types, and confidence scores.
    """
    try:
        return await cv_service.detect_ui_elements(
            image_base64=request.image,
            resize=request.resize
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Detection failed: {str(e)}"
        )


@router.post(
    "/extract-text",
    response_model=ExtractTextResponse,
    summary="Extract text from screen",
    description="Extract text from a screen capture using EasyOCR"
)
async def extract_text(
    request: ExtractTextRequest,
    cv_service: Annotated[CVService, Depends(get_cv_service)]
) -> ExtractTextResponse:
    """
    Extract text from a screen capture.

    Uses EasyOCR for accurate text recognition.
    Returns text content, positions, and confidence scores.
    """
    try:
        return await cv_service.extract_text(
            image_base64=request.image,
            resize=request.resize
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Text extraction failed: {str(e)}"
        )


@router.get(
    "/health",
    response_model=CVHealthResponse,
    summary="CV pipeline health",
    description="Get health status of CV pipeline components"
)
async def get_cv_health(
    cv_service: Annotated[CVService, Depends(get_cv_service)]
) -> CVHealthResponse:
    """
    Get health status of the CV pipeline.

    Returns status of:
    - YOLO detector (model loaded, configuration)
    - OCR engine (reader loaded, language)
    - Preprocessor (settings)
    """
    return await cv_service.get_health_status()
