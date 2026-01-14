"""
Guidance API Endpoints

REST API for AI-powered guidance generation and session management.
"""

from typing import List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_org_membership
from app.models.user import User, UserOrganisation
from app.models.guidance import SessionStatus, StepStatus
from app.schemas.guidance import (
    GenerateGuidanceRequest,
    GenerateGuidanceResponse,
    GuidanceSessionResponse,
    GuidanceSessionDetailResponse,
    GuidanceStepResponse,
    HaloTargetResponse,
    AdvanceStepRequest,
    AdvanceStepResponse,
    SkipStepRequest,
    GoToStepRequest,
    UpdateScreenRequest,
    SessionStateResponse,
    SessionListResponse,
    GuidanceHealthResponse,
    LLMHealthResponse,
    BoundingBox,
    CaptureStepRequest,
    CaptureStepResponse,
    DetectedElement,
    StartGuidanceRequest,
    StartGuidanceResponse,
)
from app.ai_engine import GuidanceGenerator, StepTracker, get_llm_client
from app.services.knowledge_service import KnowledgeService
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/guidance", tags=["guidance"])


# =============================================
# Helper Functions
# =============================================

def convert_step_to_response(step) -> GuidanceStepResponse:
    """Convert database step to response schema."""
    target = None
    if step.target_bbox:
        target = HaloTargetResponse(
            target_id=step.step_id,
            bbox=BoundingBox(**step.target_bbox),
            element_type=step.target_element_type or "unknown",
            label=step.target_element_label,
            step_number=step.step_number,
            action_type=step.action_type,
            confidence=step.match_confidence or 0.0,
        )

    return GuidanceStepResponse(
        step_id=step.step_id,
        step_number=step.step_number,
        instruction=step.instruction,
        detailed_instruction=step.detailed_instruction,
        action_type=step.action_type,
        action_value=step.action_value,
        target=target,
        match_confidence=step.match_confidence or 0.0,
        status=step.status,
    )


def convert_session_to_response(session) -> GuidanceSessionResponse:
    """Convert database session to response schema."""
    return GuidanceSessionResponse(
        session_id=session.session_id,
        query=session.query,
        status=session.status,
        current_step=session.current_step,
        total_steps=session.total_steps,
        application_context=session.application_context,
        overall_confidence=0.0,  # TODO: Calculate from steps
        created_at=session.created_at,
        updated_at=session.updated_at,
        completed_at=session.completed_at,
    )


# =============================================
# Generate Guidance
# =============================================

@router.post("/generate", response_model=GenerateGuidanceResponse)
async def generate_guidance(
    request: GenerateGuidanceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: UserOrganisation = Depends(get_current_org_membership),
):
    """
    Generate step-by-step guidance for a user query.

    This endpoint:
    1. Queries the RAG system for relevant documentation
    2. Uses LLM to generate step-by-step instructions
    3. Matches steps to detected UI elements (if screen capture provided)
    4. Creates a guidance session for tracking progress
    """
    org_id = membership.org_id

    try:
        # Step 1: Query RAG for context
        rag_results = None
        if request.kb_id or True:  # Always try to get RAG context
            knowledge_service = KnowledgeService(db)
            rag_response = await knowledge_service.rag_query(
                org_id=org_id,
                query=request.query,
                kb_id=request.kb_id,
                top_k=settings.GUIDANCE_RAG_TOP_K,
                min_similarity=0.3,
            )
            if rag_response.results:
                rag_results = [
                    {
                        "chunk_id": r.chunk_id,
                        "doc_id": r.doc_id,
                        "doc_name": r.doc_name,
                        "chunk_text": r.chunk_text,
                        "similarity": r.similarity,
                    }
                    for r in rag_response.results
                ]

        # Step 2: Generate guidance using AI engine
        generator = GuidanceGenerator()
        guidance = await generator.generate(
            query=request.query,
            rag_results=rag_results,
            screen_state=None,  # TODO: Add screen capture integration
            application_context=request.application_context,
        )

        # Check if guidance generation failed (no steps generated)
        if not guidance.steps:
            error_msg = "Failed to generate guidance steps. The LLM may be unavailable or timed out."
            logger.error(f"No steps generated: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_msg,
            )

        # Step 3: Create session in database
        tracker = StepTracker(db)
        session = await tracker.create_session(
            user_id=current_user.user_id,
            org_id=org_id,
            guidance=guidance,
            kb_id=request.kb_id,
            application_context=request.application_context,
        )

        # Step 4: Build response (sort steps since relationship doesn't have order_by for async compatibility)
        sorted_steps = sorted(session.steps, key=lambda s: s.step_number)
        steps = [convert_step_to_response(s) for s in sorted_steps]

        # Find current target
        current_target = None
        for step in steps:
            if step.status == StepStatus.CURRENT.value and step.target:
                current_target = step.target
                break

        logger.info(
            f"Generated guidance for user {current_user.user_id}: "
            f"{len(steps)} steps, session {session.session_id}"
        )

        return GenerateGuidanceResponse(
            success=True,
            session_id=session.session_id,
            query=request.query,
            total_steps=len(steps),
            context_summary=guidance.context_summary,
            overall_confidence=guidance.overall_confidence,
            steps=steps,
            current_target=current_target,
        )

    except Exception as e:
        logger.error(f"Failed to generate guidance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate guidance: {str(e)}",
        )


# =============================================
# Session Management
# =============================================

@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    status_filter: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: UserOrganisation = Depends(get_current_org_membership),
):
    """List guidance sessions for the current user."""
    tracker = StepTracker(db)
    sessions = await tracker.list_sessions(
        user_id=current_user.user_id,
        org_id=membership.org_id,
        status=status_filter,
        limit=limit,
    )

    return SessionListResponse(
        sessions=[convert_session_to_response(s) for s in sessions],
        total=len(sessions),
    )


@router.get("/sessions/{session_id}", response_model=GuidanceSessionDetailResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed guidance session information."""
    tracker = StepTracker(db)
    session = await tracker.get_session(session_id, current_user.user_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    steps = [convert_step_to_response(s) for s in sorted(session.steps, key=lambda x: x.step_number)]

    # Find current target
    current_target = None
    for step in steps:
        if step.status == StepStatus.CURRENT.value and step.target:
            current_target = step.target
            break

    return GuidanceSessionDetailResponse(
        session_id=session.session_id,
        query=session.query,
        status=session.status,
        current_step=session.current_step,
        total_steps=session.total_steps,
        application_context=session.application_context,
        context_summary=session.rag_context.get("summary") if session.rag_context else None,
        overall_confidence=0.0,
        steps=steps,
        current_target=current_target,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get("/sessions/{session_id}/state", response_model=SessionStateResponse)
async def get_session_state(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current session state for frontend."""
    tracker = StepTracker(db)
    state = await tracker.get_session_state(session_id)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SessionStateResponse(
        session_id=state.session_id,
        status=state.status,
        current_step=state.current_step,
        total_steps=state.total_steps,
        query=state.query,
        steps=state.steps,
        current_target=state.current_target,
    )


# =============================================
# Step Navigation
# =============================================

@router.post("/sessions/{session_id}/advance", response_model=AdvanceStepResponse)
async def advance_step(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Advance to the next step in the guidance session."""
    tracker = StepTracker(db)

    # Get current state first
    old_state = await tracker.get_session_state(session_id)
    if not old_state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    previous_step = old_state.current_step

    # Advance step
    new_state = await tracker.advance_step(session_id)

    is_completed = new_state.status == SessionStatus.COMPLETED.value

    # Get current target
    current_target = None
    if new_state.current_target:
        bbox = new_state.current_target.get("bbox", {})
        current_target = HaloTargetResponse(
            target_id=f"step-{new_state.current_step}",
            bbox=BoundingBox(**bbox) if bbox else BoundingBox(x1=0, y1=0, x2=0, y2=0),
            element_type=new_state.current_target.get("element_type", "unknown"),
            label=new_state.current_target.get("label"),
            step_number=new_state.current_step,
            action_type="click",
            confidence=0.0,
        )

    return AdvanceStepResponse(
        success=True,
        session_id=session_id,
        previous_step=previous_step,
        current_step=new_state.current_step,
        is_completed=is_completed,
        current_target=current_target,
        message="Guidance completed!" if is_completed else f"Moved to step {new_state.current_step}",
    )


@router.post("/sessions/{session_id}/skip", response_model=AdvanceStepResponse)
async def skip_step(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Skip the current step."""
    tracker = StepTracker(db)

    old_state = await tracker.get_session_state(session_id)
    if not old_state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    previous_step = old_state.current_step
    new_state = await tracker.skip_step(session_id)

    is_completed = new_state.status == SessionStatus.COMPLETED.value

    return AdvanceStepResponse(
        success=True,
        session_id=session_id,
        previous_step=previous_step,
        current_step=new_state.current_step,
        is_completed=is_completed,
        current_target=None,
        message="Guidance completed!" if is_completed else f"Skipped to step {new_state.current_step}",
    )


@router.post("/sessions/{session_id}/goto/{step_number}", response_model=SessionStateResponse)
async def go_to_step(
    session_id: str,
    step_number: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Jump to a specific step."""
    tracker = StepTracker(db)
    state = await tracker.go_to_step(session_id, step_number)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SessionStateResponse(
        session_id=state.session_id,
        status=state.status,
        current_step=state.current_step,
        total_steps=state.total_steps,
        query=state.query,
        steps=state.steps,
        current_target=state.current_target,
    )


# =============================================
# Session Control
# =============================================

@router.post("/sessions/{session_id}/pause")
async def pause_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pause a guidance session."""
    tracker = StepTracker(db)
    success = await tracker.pause_session(session_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return {"success": True, "message": "Session paused"}


@router.post("/sessions/{session_id}/resume", response_model=SessionStateResponse)
async def resume_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resume a paused guidance session."""
    tracker = StepTracker(db)
    state = await tracker.resume_session(session_id)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SessionStateResponse(
        session_id=state.session_id,
        status=state.status,
        current_step=state.current_step,
        total_steps=state.total_steps,
        query=state.query,
        steps=state.steps,
        current_target=state.current_target,
    )


@router.post("/sessions/{session_id}/abandon")
async def abandon_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Abandon a guidance session."""
    tracker = StepTracker(db)
    success = await tracker.abandon_session(session_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return {"success": True, "message": "Session abandoned"}


# =============================================
# Health Check
# =============================================

@router.get("/health", response_model=GuidanceHealthResponse)
async def guidance_health():
    """Check guidance engine health status."""
    # Check LLM availability
    llm_available = False
    fallback_available = False
    llm_provider = settings.LLM_PROVIDER

    # Debug logging
    logger.info(f"[Health] LLM_PROVIDER from settings: {llm_provider}")
    logger.info(f"[Health] GEMINI_API_KEY set: {bool(settings.GEMINI_API_KEY)}")

    # Get the model based on provider
    if llm_provider == "gemini":
        llm_model = settings.GEMINI_MODEL
    elif llm_provider == "openai":
        llm_model = settings.OPENAI_MODEL
    else:
        llm_model = settings.OLLAMA_MODEL

    logger.info(f"[Health] Selected model: {llm_model}")

    try:
        from app.ai_engine.llm_client import get_llm_client, GeminiClient, OpenAIClient, OllamaClient

        if llm_provider == "gemini":
            client = GeminiClient()
            llm_available = await client.health_check()
            # Check fallback (Ollama)
            fallback_client = OllamaClient()
            fallback_available = await fallback_client.health_check()
        elif llm_provider == "openai":
            client = OpenAIClient()
            llm_available = await client.health_check()
            fallback_client = OllamaClient()
            fallback_available = await fallback_client.health_check()
        else:
            client = OllamaClient()
            llm_available = await client.health_check()
            fallback_client = GeminiClient()
            fallback_available = await fallback_client.health_check()
    except Exception as e:
        logger.error(f"LLM health check error: {e}")

    return GuidanceHealthResponse(
        status="healthy" if llm_available else "degraded",
        llm=LLMHealthResponse(
            status="available" if llm_available else "unavailable",
            provider=llm_provider,
            model=llm_model,
            available=llm_available,
            fallback_available=fallback_available,
        ),
        rag_available=True,  # RAG is always available if DB is up
        cv_available=True,  # CV pipeline is always available
    )


# =============================================
# Step Capture & Halo Integration
# =============================================

@router.post("/sessions/{session_id}/start", response_model=StartGuidanceResponse)
async def start_guidance_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: UserOrganisation = Depends(get_current_org_membership),
):
    """
    Start active guidance for a session.

    This endpoint:
    1. Checks if target application is configured for the org
    2. Finds the target window on the user's desktop
    3. Captures and analyzes the window
    4. Matches the first step to detected UI elements
    5. Returns the Halo target for the first step
    """
    from sqlalchemy import select
    from app.models.organisation import Organisation
    from app.services.window_capture import get_window_capture_service
    from app.services.cv_service import get_cv_service
    from app.ai_engine.matcher import ElementMatcher, TargetSpec, UIElement
    import time

    # Get session
    tracker = StepTracker(db)
    session = await tracker.get_session(session_id, current_user.user_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Get organisation target app settings
    result = await db.execute(
        select(Organisation).where(Organisation.org_id == membership.org_id)
    )
    organisation = result.scalar_one_or_none()

    if not organisation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found",
        )

    target_app_configured = organisation.has_target_app_configured

    if not target_app_configured:
        return StartGuidanceResponse(
            success=True,
            session_id=session_id,
            status=session.status,
            current_step=session.current_step,
            total_steps=session.total_steps,
            target_app_configured=False,
            target_window_found=False,
            target_window_title=None,
            current_target=None,
            message="Target application not configured. Please configure in organisation settings.",
        )

    # Find target window
    window_service = get_window_capture_service()
    image_base64, window = window_service.capture_window_by_pattern(
        pattern=organisation.target_window_pattern,
        process_name=organisation.target_process_name,
    )

    if not window:
        return StartGuidanceResponse(
            success=True,
            session_id=session_id,
            status=session.status,
            current_step=session.current_step,
            total_steps=session.total_steps,
            target_app_configured=True,
            target_window_found=False,
            target_window_title=None,
            current_target=None,
            message=f"Target window not found. Please open {organisation.target_app_name or 'the target application'}.",
        )

    # Analyze captured screen
    current_target = None
    if image_base64:
        try:
            cv_service = get_cv_service()
            start_time = time.time()
            screen_state = await cv_service.analyze_screen(image_base64)
            elapsed = (time.time() - start_time) * 1000

            # Get current step
            current_step_obj = None
            for step in sorted(session.steps, key=lambda s: s.step_number):
                if step.status == StepStatus.CURRENT.value:
                    current_step_obj = step
                    break

            if current_step_obj and screen_state.elements:
                # Convert to UIElement format
                ui_elements = [
                    UIElement(
                        element_id=elem.element_id,
                        type=elem.type,
                        label=elem.label,
                        bbox={
                            "x1": elem.bbox.x1,
                            "y1": elem.bbox.y1,
                            "x2": elem.bbox.x2,
                            "y2": elem.bbox.y2,
                        },
                        confidence=elem.confidence,
                        metadata=elem.metadata,
                    )
                    for elem in screen_state.elements
                ]

                # Match step to elements
                matcher = ElementMatcher()
                target_spec = TargetSpec(
                    element_type=current_step_obj.target_element_type,
                    label=current_step_obj.target_element_label,
                    action=current_step_obj.action_type,
                )

                match_result = matcher.match_element(target_spec, ui_elements)

                if match_result:
                    current_target = HaloTargetResponse(
                        target_id=match_result.element.element_id,
                        bbox=BoundingBox(
                            x1=match_result.element.bbox["x1"],
                            y1=match_result.element.bbox["y1"],
                            x2=match_result.element.bbox["x2"],
                            y2=match_result.element.bbox["y2"],
                        ),
                        element_type=match_result.element.type,
                        label=match_result.element.label,
                        step_number=current_step_obj.step_number,
                        action_type=current_step_obj.action_type,
                        confidence=match_result.confidence,
                    )

            logger.info(f"Screen analyzed in {elapsed:.0f}ms, {len(screen_state.elements)} elements found")

        except Exception as e:
            logger.error(f"Failed to analyze screen: {e}")

    return StartGuidanceResponse(
        success=True,
        session_id=session_id,
        status=session.status,
        current_step=session.current_step,
        total_steps=session.total_steps,
        target_app_configured=True,
        target_window_found=True,
        target_window_title=window.title,
        current_target=current_target,
        message="Guidance started. Follow the highlighted elements.",
    )


@router.post("/sessions/{session_id}/capture", response_model=CaptureStepResponse)
async def capture_step(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: UserOrganisation = Depends(get_current_org_membership),
    request: Optional[CaptureStepRequest] = Body(default=None),
):
    """
    Capture and analyze screen for the current step.

    This endpoint:
    1. Uses provided screenshot from frontend (Tauri) OR captures the target application window
    2. Runs CV analysis (UI detection + OCR)
    3. Matches the current step instruction to detected elements
    4. Returns the Halo target coordinates
    """
    from sqlalchemy import select
    from app.models.organisation import Organisation
    from app.services.window_capture import get_window_capture_service
    from app.services.cv_service import get_cv_service
    from app.ai_engine.matcher import ElementMatcher, TargetSpec, UIElement
    import time

    start_time = time.time()

    # Get session
    tracker = StepTracker(db)
    session = await tracker.get_session(session_id, current_user.user_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Get current step
    current_step_obj = None
    for step in sorted(session.steps, key=lambda s: s.step_number):
        if step.status == StepStatus.CURRENT.value:
            current_step_obj = step
            break

    if not current_step_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No current step found in session",
        )

    # Get organisation target app settings
    result = await db.execute(
        select(Organisation).where(Organisation.org_id == membership.org_id)
    )
    organisation = result.scalar_one_or_none()

    if not organisation or not organisation.has_target_app_configured:
        return CaptureStepResponse(
            success=False,
            session_id=session_id,
            step_number=current_step_obj.step_number,
            instruction=current_step_obj.instruction,
            target_found=False,
            target=None,
            all_elements=[],
            capture_time_ms=0,
            match_confidence=0,
            message="Target application not configured for this organisation.",
            window_title=None,
        )

    # Check if frontend provided a screenshot (Tauri capture)
    image_base64 = None
    window_title = None

    if request and request.image_base64:
        # Use image from frontend (Tauri captured it)
        logger.info("Using screenshot provided by frontend (Tauri capture)")
        image_base64 = request.image_base64
        window_title = "Captured by frontend"  # Frontend doesn't provide window title with screenshot
    else:
        # Fall back to backend window capture (legacy approach)
        logger.info("No frontend screenshot provided, attempting backend window capture")
        window_service = get_window_capture_service()

        image_base64, window = window_service.capture_window_by_pattern(
            pattern=organisation.target_window_pattern,
            process_name=organisation.target_process_name,
        )

        if window:
            window_title = window.title
        else:
            return CaptureStepResponse(
                success=False,
                session_id=session_id,
                step_number=current_step_obj.step_number,
                instruction=current_step_obj.instruction,
                target_found=False,
                target=None,
                all_elements=[],
                capture_time_ms=(time.time() - start_time) * 1000,
                match_confidence=0,
                message=f"Target window not found. Please open {organisation.target_app_name or 'the target application'}.",
                window_title=None,
            )

    if not image_base64:
        return CaptureStepResponse(
            success=False,
            session_id=session_id,
            step_number=current_step_obj.step_number,
            instruction=current_step_obj.instruction,
            target_found=False,
            target=None,
            all_elements=[],
            capture_time_ms=(time.time() - start_time) * 1000,
            match_confidence=0,
            message="Failed to capture window screenshot.",
            window_title=window_title,
        )

    # Analyze screen
    try:
        cv_service = get_cv_service()
        screen_state = await cv_service.analyze_screen(image_base64)
    except Exception as e:
        logger.error(f"CV analysis failed: {e}")
        return CaptureStepResponse(
            success=False,
            session_id=session_id,
            step_number=current_step_obj.step_number,
            instruction=current_step_obj.instruction,
            target_found=False,
            target=None,
            all_elements=[],
            capture_time_ms=(time.time() - start_time) * 1000,
            match_confidence=0,
            message=f"Screen analysis failed: {str(e)}",
            window_title=window_title,
        )

    # Helper function to enrich element labels using nearby OCR text regions
    def enrich_element_labels_from_ocr(elements, text_regions, max_distance=100):
        """
        For elements without labels, find nearby OCR text and use it as the label.
        This is a fallback when icon captioning fails.

        Priority:
        1. Text that overlaps the element
        2. Text that is immediately adjacent (within element height)
        3. Text that is nearby (within max_distance)
        """
        enriched_count = 0
        for elem in elements:
            if elem.label:  # Skip elements that already have labels
                continue

            elem_bbox = elem.bbox
            elem_center_x = (elem_bbox.x1 + elem_bbox.x2) / 2
            elem_center_y = (elem_bbox.y1 + elem_bbox.y2) / 2
            elem_height = elem_bbox.y2 - elem_bbox.y1
            elem_width = elem_bbox.x2 - elem_bbox.x1

            # Find OCR text regions that overlap with or are near this element
            best_text = None
            best_distance = float('inf')
            best_priority = 999  # Lower is better

            for region in text_regions:
                region_bbox = region.bbox
                region_center_x = (region_bbox.x1 + region_bbox.x2) / 2
                region_center_y = (region_bbox.y1 + region_bbox.y2) / 2

                # Check if OCR region overlaps with element
                overlaps = (
                    elem_bbox.x1 <= region_bbox.x2 and elem_bbox.x2 >= region_bbox.x1 and
                    elem_bbox.y1 <= region_bbox.y2 and elem_bbox.y2 >= region_bbox.y1
                )

                if overlaps:
                    # Priority 1: Text overlaps the element - use it immediately
                    elem.label = region.text
                    enriched_count += 1
                    best_text = None  # Mark as already assigned
                    break

                # Calculate distance from element center to text center
                distance = ((elem_center_x - region_center_x) ** 2 + (elem_center_y - region_center_y) ** 2) ** 0.5

                # Priority 2: Text immediately to the right or below (common UI patterns)
                is_right_adjacent = (
                    abs(region_bbox.y1 - elem_bbox.y1) < elem_height * 0.5 and  # Same vertical level
                    region_bbox.x1 >= elem_bbox.x2 and  # To the right
                    region_bbox.x1 - elem_bbox.x2 < elem_width * 2  # Within 2x element width
                )
                is_below_adjacent = (
                    abs(region_center_x - elem_center_x) < elem_width * 0.5 and  # Same horizontal level
                    region_bbox.y1 >= elem_bbox.y2 and  # Below
                    region_bbox.y1 - elem_bbox.y2 < elem_height * 2  # Within 2x element height
                )

                if is_right_adjacent or is_below_adjacent:
                    priority = 2
                    if priority < best_priority or (priority == best_priority and distance < best_distance):
                        best_priority = priority
                        best_distance = distance
                        best_text = region.text
                elif distance < max_distance:
                    # Priority 3: Nearby text
                    priority = 3
                    if priority < best_priority or (priority == best_priority and distance < best_distance):
                        best_priority = priority
                        best_distance = distance
                        best_text = region.text

            # Use the best text found if no overlap was assigned
            if not elem.label and best_text:
                elem.label = best_text
                enriched_count += 1

        return enriched_count

    # Always try to enrich element labels from OCR (icon captioning often fails)
    elements_without_labels = sum(1 for elem in screen_state.elements if not elem.label)
    logger.info(f"[CAPTURE_STEP] {elements_without_labels}/{len(screen_state.elements)} elements lack labels, {len(screen_state.text_regions)} OCR text regions available")

    if elements_without_labels > 0 and len(screen_state.text_regions) > 0:
        enriched = enrich_element_labels_from_ocr(screen_state.elements, screen_state.text_regions)
        logger.info(f"[CAPTURE_STEP] Enriched {enriched} element labels from OCR text regions")

        # Log some sample enriched labels
        sample_labels = [elem.label for elem in screen_state.elements[:10] if elem.label]
        logger.info(f"[CAPTURE_STEP] Sample element labels after enrichment: {sample_labels[:5]}")

    # Convert elements to response format
    all_elements = [
        DetectedElement(
            element_id=elem.element_id,
            element_type=elem.type,
            label=elem.label,
            bbox=BoundingBox(
                x1=elem.bbox.x1,
                y1=elem.bbox.y1,
                x2=elem.bbox.x2,
                y2=elem.bbox.y2,
            ),
            confidence=elem.confidence,
            metadata=elem.metadata,
        )
        for elem in screen_state.elements
    ]

    # Convert to UIElement format for matching
    ui_elements = [
        UIElement(
            element_id=elem.element_id,
            type=elem.type,
            label=elem.label,
            bbox={
                "x1": elem.bbox.x1,
                "y1": elem.bbox.y1,
                "x2": elem.bbox.x2,
                "y2": elem.bbox.y2,
            },
            confidence=elem.confidence,
            metadata=elem.metadata,
        )
        for elem in screen_state.elements
    ]

    # Match step to elements
    matcher = ElementMatcher()

    # If target_element_label is None, try to extract it from the instruction
    target_label = current_step_obj.target_element_label
    extracted_keywords = []

    logger.info(f"[CAPTURE_STEP] Instruction: {current_step_obj.instruction}, original target_label: {target_label}")
    print(f"[CAPTURE_STEP] Instruction: {current_step_obj.instruction}, original target_label: {target_label}")

    if not target_label and current_step_obj.instruction:
        # Extract quoted text or button/link names from instruction
        import re
        # Match quoted text like "Sign in" or 'New Issue'
        quoted = re.findall(r'["\']([^"\']+)["\']', current_step_obj.instruction)
        # Match "the X button" or "click X" patterns
        button_match = re.findall(r'(?:click|press|tap|select|the)\s+(?:the\s+)?["\']?(\w+(?:\s+\w+)?)["\']?\s+(?:button|link|tab|option|menu)',
                                   current_step_obj.instruction, re.IGNORECASE)

        if quoted:
            target_label = quoted[0]  # Use first quoted text
            logger.info(f"Extracted target label from quoted text: '{target_label}'")
        elif button_match:
            target_label = button_match[0]
            logger.info(f"Extracted target label from pattern: '{target_label}'")
        else:
            # FALLBACK: Use the instruction itself as the label
            # This allows substring matching (e.g., "Enter your email" matches "Enter your email address")
            target_label = current_step_obj.instruction
            logger.info(f"Using instruction as target label for matching: '{target_label}'")

        # Also extract keywords from instruction for fallback matching
        # Look for common UI element names
        words = current_step_obj.instruction.lower().split()
        ui_keywords = ['sign', 'login', 'submit', 'create', 'new', 'search', 'menu', 'settings',
                       'profile', 'save', 'cancel', 'delete', 'edit', 'add', 'remove', 'open', 'close',
                       'email', 'username', 'password', 'name', 'enter', 'type', 'fill']
        extracted_keywords = [w for w in words if w in ui_keywords]

    logger.info(f"[CAPTURE_STEP] After extraction - target_label: {target_label}, keywords: {extracted_keywords}")
    print(f"[CAPTURE_STEP] After extraction - target_label: {target_label}, keywords: {extracted_keywords}")

    target_spec = TargetSpec(
        element_type=current_step_obj.target_element_type,
        label=target_label,
        keywords=extracted_keywords if extracted_keywords else None,
        action=current_step_obj.action_type,
    )

    logger.info(f"Step {current_step_obj.step_number} target spec: type={target_spec.element_type}, label={target_spec.label}, keywords={target_spec.keywords}, action={target_spec.action}")
    logger.info(f"Detected {len(ui_elements)} UI elements. Sample labels: {[e.label for e in ui_elements[:10] if e.label]}")
    print(f"[CAPTURE_STEP] Target spec: type={target_spec.element_type}, label='{target_spec.label}', keywords={target_spec.keywords}, action={target_spec.action}")
    print(f"[CAPTURE_STEP] {len(ui_elements)} UI elements. Sample labels: {[e.label for e in ui_elements[:10] if e.label]}")

    match_result = matcher.match_element(target_spec, ui_elements)
    capture_time = (time.time() - start_time) * 1000

    if match_result:
        target = HaloTargetResponse(
            target_id=match_result.element.element_id,
            bbox=BoundingBox(
                x1=match_result.element.bbox["x1"],
                y1=match_result.element.bbox["y1"],
                x2=match_result.element.bbox["x2"],
                y2=match_result.element.bbox["y2"],
            ),
            element_type=match_result.element.type,
            label=match_result.element.label,
            step_number=current_step_obj.step_number,
            action_type=current_step_obj.action_type,
            confidence=match_result.confidence,
        )

        return CaptureStepResponse(
            success=True,
            session_id=session_id,
            step_number=current_step_obj.step_number,
            instruction=current_step_obj.instruction,
            target_found=True,
            target=target,
            all_elements=all_elements,
            capture_time_ms=capture_time,
            match_confidence=match_result.confidence,
            message=f"Target element found: {match_result.element.label or match_result.element.type}",
            window_title=window_title,
        )
    else:
        return CaptureStepResponse(
            success=True,
            session_id=session_id,
            step_number=current_step_obj.step_number,
            instruction=current_step_obj.instruction,
            target_found=False,
            target=None,
            all_elements=all_elements,
            capture_time_ms=capture_time,
            match_confidence=0,
            message=f"Target element not found. {len(all_elements)} elements detected.",
            window_title=window_title,
        )
