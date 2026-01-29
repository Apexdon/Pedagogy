"""
Guidance Schemas

Pydantic models for guidance API requests and responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# =============================================
# Request Schemas
# =============================================

class GenerateGuidanceRequest(BaseModel):
    """Request to generate new guidance."""
    query: str = Field(..., min_length=1, description="User's question or task description")
    kb_id: Optional[str] = Field(None, description="Specific knowledge base to use")
    application_context: Optional[str] = Field(None, description="Current application context")
    include_screen_capture: bool = Field(True, description="Whether to capture and analyze screen")


class AdvanceStepRequest(BaseModel):
    """Request to advance to next step."""
    session_id: str


class SkipStepRequest(BaseModel):
    """Request to skip current step."""
    session_id: str


class GoToStepRequest(BaseModel):
    """Request to jump to specific step."""
    session_id: str
    step_number: int = Field(..., ge=1)


class UpdateScreenRequest(BaseModel):
    """Request to update targets with new screen state."""
    session_id: str
    screen_state: Dict[str, Any] = Field(..., description="Screen state from CV pipeline")


class AddCaptureRequest(BaseModel):
    """Request to add capture to session."""
    session_id: str
    step_id: Optional[str] = None
    screen_state: Dict[str, Any]
    capture_type: str = Field("step", pattern="^(initial|step|verification)$")
    screenshot_base64: Optional[str] = None


# =============================================
# Response Schemas
# =============================================

class BoundingBox(BaseModel):
    """Bounding box coordinates."""
    x1: int
    y1: int
    x2: int
    y2: int


class HaloTargetResponse(BaseModel):
    """Target for Halo visual highlighting."""
    target_id: str
    bbox: BoundingBox
    element_type: str
    label: Optional[str]
    step_number: int
    action_type: str
    confidence: float


class GuidanceStepResponse(BaseModel):
    """Single guidance step."""
    step_id: str
    step_number: int
    instruction: str
    detailed_instruction: Optional[str] = None
    action_type: str
    action_value: Optional[str] = None
    target: Optional[HaloTargetResponse] = None
    match_confidence: float = 0.0
    status: str = "pending"


class GuidanceSessionResponse(BaseModel):
    """Guidance session summary."""
    session_id: str
    query: str
    status: str
    current_step: int
    total_steps: int
    application_context: Optional[str] = None
    overall_confidence: float = 0.0
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class GuidanceSessionDetailResponse(BaseModel):
    """Detailed guidance session with all steps."""
    session_id: str
    query: str
    status: str
    current_step: int
    total_steps: int
    application_context: Optional[str] = None
    context_summary: Optional[str] = None
    overall_confidence: float = 0.0
    steps: List[GuidanceStepResponse]
    current_target: Optional[HaloTargetResponse] = None
    created_at: datetime
    updated_at: datetime


class GenerateGuidanceResponse(BaseModel):
    """Response from guidance generation."""
    success: bool
    session_id: str
    query: str
    total_steps: int
    context_summary: Optional[str] = None
    overall_confidence: float
    steps: List[GuidanceStepResponse]
    current_target: Optional[HaloTargetResponse] = None


class SessionStateResponse(BaseModel):
    """Current session state for frontend."""
    session_id: str
    status: str
    current_step: int
    total_steps: int
    query: str
    steps: List[Dict[str, Any]]
    current_target: Optional[Dict[str, Any]] = None


class AdvanceStepResponse(BaseModel):
    """Response after advancing step."""
    success: bool
    session_id: str
    previous_step: int
    current_step: int
    is_completed: bool
    current_target: Optional[HaloTargetResponse] = None
    message: str


class SessionListResponse(BaseModel):
    """List of guidance sessions."""
    sessions: List[GuidanceSessionResponse]
    total: int


class GuidanceCaptureResponse(BaseModel):
    """Guidance capture record."""
    capture_id: str
    session_id: str
    step_id: Optional[str]
    capture_type: str
    element_count: int
    text_region_count: int
    processing_time_ms: Optional[float]
    captured_at: datetime


class LLMHealthResponse(BaseModel):
    """LLM health status."""
    status: str
    provider: str
    model: str
    available: bool
    fallback_available: bool


class GuidanceHealthResponse(BaseModel):
    """Guidance engine health status."""
    status: str
    llm: LLMHealthResponse
    rag_available: bool
    cv_available: bool


# =============================================
# Step Capture Schemas (for per-step CV analysis)
# =============================================

class CaptureStepRequest(BaseModel):
    """Request to capture and analyze screen for current step."""
    image_base64: Optional[str] = Field(None, description="Base64 encoded screenshot from frontend (Tauri)")
    force_capture: bool = Field(False, description="Force new capture even if recent one exists")
    hwnd: Optional[int] = Field(None, description="Window handle for HWND caching (visual verification)")
    skip_verification: bool = Field(False, description="Skip visual verification (use if already verified)")


class DetectedElement(BaseModel):
    """Detected UI element from CV pipeline."""
    element_id: str
    element_type: str
    label: Optional[str] = None
    bbox: BoundingBox
    confidence: float
    metadata: Dict[str, Any] = {}


class CaptureStepResponse(BaseModel):
    """Response from step capture with matched target."""
    success: bool
    session_id: str
    step_number: int
    instruction: str
    target_found: bool
    target: Optional[HaloTargetResponse] = None
    all_elements: List[DetectedElement] = []
    capture_time_ms: float = 0.0
    match_confidence: float = 0.0
    message: str
    window_title: Optional[str] = None
    # Visual verification fields
    target_verified: bool = True  # Whether target app was verified via brand keywords
    verification_keywords_matched: List[str] = []  # Which keywords were found
    hwnd_cached: bool = False  # Whether HWND was cached for future quick checks


class StartGuidanceRequest(BaseModel):
    """Request to start active guidance (triggers first capture)."""
    session_id: str = Field(..., description="Generated guidance session ID")


class StartGuidanceResponse(BaseModel):
    """Response when starting active guidance."""
    success: bool
    session_id: str
    status: str
    current_step: int
    total_steps: int
    target_app_configured: bool
    target_window_found: bool
    target_window_title: Optional[str] = None
    current_target: Optional[HaloTargetResponse] = None
    message: str


# =============================================
# Fast Visual Verification Schemas
# =============================================

class FastVerifyRequest(BaseModel):
    """Request for fast visual verification (OCR-only, no UI detection)."""
    image_base64: str = Field(..., description="Base64 encoded screenshot")
    brand_keywords: List[str] = Field(..., description="Keywords to search for in OCR text")
    hwnd: Optional[int] = Field(None, description="Window handle for HWND caching")


class FastVerifyResponse(BaseModel):
    """Response from fast visual verification."""
    success: bool
    is_verified: bool
    matched_keywords: List[str] = []
    confidence: float = 0.0
    verification_time_ms: float = 0.0
    ocr_time_ms: float = 0.0
    total_time_ms: float = 0.0
    hwnd_cached: bool = False
    page_hash_cached: bool = False  # True if verified from perceptual hash cache
    verification_method: str = "ocr"  # "page_hash", "hwnd", "ocr", "none"
    message: str


# =============================================
# Fast Position Update Schemas (for scroll handling)
# =============================================

class FastPositionUpdateRequest(BaseModel):
    """Request for fast halo position update using scroll offset detection."""
    image_base64: str = Field(..., description="Base64 encoded screenshot")
    target_label: str = Field(..., description="The label text to find")
    current_bbox: Optional[BoundingBox] = Field(None, description="Current bounding box for scroll offset calculation")
    session_id: Optional[str] = Field(None, description="Session ID for reference image tracking")


class FastPositionUpdateResponse(BaseModel):
    """Response from fast position update."""
    success: bool
    found: bool
    new_bbox: Optional[BoundingBox] = None
    confidence: float = 0.0
    scroll_offset_y: int = 0  # Scroll offset detected (positive = scrolled down)
    detection_method: str = "none"  # "scroll_offset", "ocr_fallback", or "none"
    processing_time_ms: float = 0.0
    total_time_ms: float = 0.0
    message: str
    reference_stored: bool = False  # Whether a new reference image was stored
