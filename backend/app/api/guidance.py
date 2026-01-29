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
    FastVerifyRequest,
    FastVerifyResponse,
    FastPositionUpdateRequest,
    FastPositionUpdateResponse,
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


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a guidance session and all related data."""
    tracker = StepTracker(db)
    success = await tracker.delete_session(session_id, current_user.user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return {"success": True, "message": "Session deleted"}


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
    from app.models.target_application import TargetApplication
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

    # Get organisation
    result = await db.execute(
        select(Organisation).where(Organisation.org_id == membership.org_id)
    )
    organisation = result.scalar_one_or_none()

    if not organisation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found",
        )

    # Check for target application - first try new TargetApplication table, then fall back to legacy org fields
    target_app_result = await db.execute(
        select(TargetApplication)
        .where(TargetApplication.org_id == membership.org_id)
        .where(TargetApplication.is_active == True)
        .order_by(TargetApplication.is_default.desc())  # Default app first
        .limit(1)
    )
    target_app = target_app_result.scalar_one_or_none()

    # Determine if target app is configured (new model OR legacy org fields)
    target_app_configured = (
        (target_app and target_app.is_configured) or
        organisation.has_target_app_configured
    )

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
            message="Target application not configured. Please configure in Target Apps settings.",
        )

    # Get window pattern and process name from target app or legacy org fields
    window_pattern = (
        target_app.window_pattern if target_app else None
    ) or organisation.target_window_pattern
    process_name = (
        target_app.process_name if target_app else None
    ) or organisation.target_process_name
    app_name = (
        target_app.app_name if target_app else None
    ) or organisation.target_app_name

    # Find target window
    window_service = get_window_capture_service()
    image_base64, window = window_service.capture_window_by_pattern(
        pattern=window_pattern,
        process_name=process_name,
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
            message=f"Target window not found. Please open {app_name or 'the target application'}.",
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
    from app.models.target_application import TargetApplication
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

    # Get organisation
    result = await db.execute(
        select(Organisation).where(Organisation.org_id == membership.org_id)
    )
    organisation = result.scalar_one_or_none()

    if not organisation:
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
            message="Organisation not found.",
            window_title=None,
        )

    # Check for target application - first try new TargetApplication table, then fall back to legacy org fields
    target_app_result = await db.execute(
        select(TargetApplication)
        .where(TargetApplication.org_id == membership.org_id)
        .where(TargetApplication.is_active == True)
        .order_by(TargetApplication.is_default.desc())  # Default app first
        .limit(1)
    )
    target_app = target_app_result.scalar_one_or_none()

    # Determine if target app is configured (new model OR legacy org fields)
    has_target_configured = (
        (target_app and target_app.is_configured) or
        organisation.has_target_app_configured
    )

    if not has_target_configured:
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
            message="Target application not configured for this organisation. Please configure in Target Apps settings.",
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

        # Get window pattern and process name from target app or legacy org fields
        window_pattern = (
            target_app.window_pattern if target_app else None
        ) or organisation.target_window_pattern
        process_name = (
            target_app.process_name if target_app else None
        ) or organisation.target_process_name
        app_name = (
            target_app.app_name if target_app else None
        ) or organisation.target_app_name

        image_base64, window = window_service.capture_window_by_pattern(
            pattern=window_pattern,
            process_name=process_name,
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
                message=f"Target window not found. Please open {app_name or 'the target application'}.",
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

    # ==========================================
    # Visual Verification using Brand Keywords
    # ==========================================
    # This verifies we're looking at the target application by checking
    # for brand keywords in the OCR text. Uses the SAME OCR data already
    # extracted by CV analysis - no duplicate processing.
    from app.services.target_verifier import get_target_verifier

    target_verified = True
    verification_keywords_matched = []
    hwnd_cached = False
    hwnd = request.hwnd if request else None

    # Get brand keywords from target app config
    brand_keywords = []
    if target_app:
        brand_keywords = target_app.effective_brand_keywords

    if brand_keywords and not (request and request.skip_verification):
        verifier = get_target_verifier()

        # Convert screen_state.text_regions to dict format for verifier
        text_regions_for_verify = [
            {"text": region.text}
            for region in screen_state.text_regions
        ]

        verification_result = verifier.verify_by_keywords(
            text_regions=text_regions_for_verify,
            brand_keywords=brand_keywords,
            hwnd=hwnd,
        )

        target_verified = verification_result.is_verified
        verification_keywords_matched = verification_result.matched_keywords
        hwnd_cached = hwnd is not None and verification_result.is_verified

        if not target_verified:
            # Not the target application - return early without element matching
            logger.warning(f"[CAPTURE_STEP] Visual verification failed - not on target app. Looking for: {brand_keywords}")
            return CaptureStepResponse(
                success=True,  # Capture succeeded, but wrong app
                session_id=session_id,
                step_number=current_step_obj.step_number,
                instruction=current_step_obj.instruction,
                target_found=False,
                target=None,
                all_elements=[],  # Don't return elements for wrong app
                capture_time_ms=(time.time() - start_time) * 1000,
                match_confidence=0,
                message=f"Please navigate to the target application. Looking for: {', '.join(brand_keywords)}",
                window_title=window_title,
                target_verified=False,
                verification_keywords_matched=[],
                hwnd_cached=False,
            )

        logger.info(f"[CAPTURE_STEP] Visual verification passed! Matched keywords: {verification_keywords_matched}")

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
            target_verified=target_verified,
            verification_keywords_matched=verification_keywords_matched,
            hwnd_cached=hwnd_cached,
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
            target_verified=target_verified,
            verification_keywords_matched=verification_keywords_matched,
            hwnd_cached=hwnd_cached,
        )


# =============================================
# Fast Visual Verification (OCR-only)
# =============================================

@router.post("/verify-target", response_model=FastVerifyResponse)
async def fast_verify_target(
    request: FastVerifyRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Fast visual verification using multi-tier caching and optimized OCR.

    Verification tiers (in order of speed):
    1. Perceptual hash cache (~1ms) - Matches previously verified pages
    2. HWND cache (~1ms) - Matches previously verified window handles
    3. Fast OCR (~200-400ms) - Header-only ROI with RapidOCR/Windows OCR

    This endpoint is designed for quick target application verification
    and runs every 1 second during guidance sessions.

    Performance optimizations:
    - Perceptual hash cache: Skip OCR when navigating between verified pages
    - HWND cache: Skip OCR when same window is still active
    - Header-only ROI: Only OCR top 250px where brand text appears
    - RapidOCR: 30-50% faster than Tesseract with better accuracy
    """
    import time

    start_time = time.time()

    # Import verification services
    from app.services.target_verifier import get_target_verifier, get_hwnd_cache
    from app.services.page_hash_cache import get_fast_verification_with_hash

    hwnd_cache = get_hwnd_cache()
    fast_verify_service = get_fast_verification_with_hash()

    # =========================================
    # TIER 1: Perceptual Hash Cache (instant)
    # =========================================
    # Check if this exact page was previously verified
    try:
        is_hash_match, hash_method = fast_verify_service.quick_verify(
            image_base64=request.image_base64,
            hwnd=request.hwnd,
        )

        if is_hash_match:
            total_time = (time.time() - start_time) * 1000
            logger.info(f"[FAST_VERIFY] Page hash MATCH in {total_time:.1f}ms - skipping OCR")
            return FastVerifyResponse(
                success=True,
                is_verified=True,
                matched_keywords=["(page cached)"],
                confidence=1.0,
                verification_time_ms=0.0,
                ocr_time_ms=0.0,
                total_time_ms=total_time,
                hwnd_cached=False,
                page_hash_cached=True,
                verification_method="page_hash",
                message="Target verified from page hash cache (previously visited page)",
            )
    except Exception as e:
        logger.warning(f"[FAST_VERIFY] Page hash check failed: {e}")
        # Continue to other verification methods

    # =========================================
    # TIER 2: HWND Cache (instant)
    # =========================================
    if request.hwnd is not None and hwnd_cache.is_verified(request.hwnd):
        total_time = (time.time() - start_time) * 1000
        logger.info(f"[FAST_VERIFY] HWND {request.hwnd} cached - verified in {total_time:.1f}ms")
        return FastVerifyResponse(
            success=True,
            is_verified=True,
            matched_keywords=["(hwnd cached)"],
            confidence=1.0,
            verification_time_ms=0.0,
            ocr_time_ms=0.0,
            total_time_ms=total_time,
            hwnd_cached=True,
            page_hash_cached=False,
            verification_method="hwnd",
            message="Target verified from HWND cache",
        )

    # =========================================
    # TIER 3: Fast OCR Verification
    # =========================================
    if not request.brand_keywords:
        return FastVerifyResponse(
            success=True,
            is_verified=True,  # No keywords = no verification needed
            matched_keywords=[],
            confidence=0.0,
            verification_time_ms=0.0,
            ocr_time_ms=0.0,
            total_time_ms=(time.time() - start_time) * 1000,
            hwnd_cached=False,
            page_hash_cached=False,
            verification_method="none",
            message="No brand keywords configured - verification skipped",
        )

    try:
        from app.services.cv_service import get_cv_service

        cv_service = get_cv_service()
        ocr_start = time.time()

        # Use header-only ROI for faster OCR (brand text is in header)
        # RapidOCR/Windows OCR is ~200-400ms vs Tesseract ~500-700ms
        ocr_result = cv_service.context_engine.extract_text_fast(
            request.image_base64,
            resize=True,
            max_width=1280,
            max_height=720,
            use_header_roi=True,  # Only OCR top portion (where brand text is)
            header_roi_height=250,  # Top 250 pixels
        )

        ocr_time = (time.time() - ocr_start) * 1000
        print(f"[FAST_VERIFY] OCR completed in {ocr_time:.0f}ms, found {len(ocr_result.text_regions)} text regions")

        # Run keyword verification
        verifier = get_target_verifier()
        verify_start = time.time()

        text_regions_for_verify = [
            {"text": region.text}
            for region in ocr_result.text_regions
        ]

        verification_result = verifier.verify_by_keywords(
            text_regions=text_regions_for_verify,
            brand_keywords=request.brand_keywords,
            hwnd=request.hwnd,
        )

        verify_time = (time.time() - verify_start) * 1000
        total_time = (time.time() - start_time) * 1000

        if verification_result.is_verified:
            # Add this page to the hash cache for future instant verification
            try:
                fast_verify_service.add_verified_page(request.image_base64)
            except Exception as e:
                logger.warning(f"[FAST_VERIFY] Failed to cache page hash: {e}")

            # Print prominent message to console
            print(f"\n{'='*60}")
            print(f"✓ TARGET VERIFIED in {total_time:.0f}ms")
            print(f"  Matched keywords: {verification_result.matched_keywords}")
            print(f"{'='*60}\n")

            logger.info(
                f"[FAST_VERIFY] Target VERIFIED via OCR in {total_time:.0f}ms. "
                f"Matched: {verification_result.matched_keywords}"
            )
            message = f"Target verified! Matched: {', '.join(verification_result.matched_keywords)}"
        else:
            print(f"[FAST_VERIFY] Target NOT verified in {total_time:.0f}ms. Looking for: {request.brand_keywords}")
            message = f"Target not verified. Looking for: {', '.join(request.brand_keywords)}"

        return FastVerifyResponse(
            success=True,
            is_verified=verification_result.is_verified,
            matched_keywords=verification_result.matched_keywords,
            confidence=verification_result.confidence,
            verification_time_ms=verify_time,
            ocr_time_ms=ocr_time,
            total_time_ms=total_time,
            hwnd_cached=request.hwnd is not None and verification_result.is_verified,
            page_hash_cached=False,
            verification_method="ocr",
            message=message,
        )

    except Exception as e:
        logger.error(f"[FAST_VERIFY] Error during verification: {e}")
        return FastVerifyResponse(
            success=False,
            is_verified=False,
            matched_keywords=[],
            confidence=0.0,
            verification_time_ms=0.0,
            ocr_time_ms=0.0,
            total_time_ms=(time.time() - start_time) * 1000,
            hwnd_cached=False,
            page_hash_cached=False,
            verification_method="error",
            message=f"Verification failed: {str(e)}",
        )


# =============================================
# Fast Position Update (Scroll Offset Detection)
# =============================================

@router.post("/update-position", response_model=FastPositionUpdateResponse)
async def fast_position_update(
    request: FastPositionUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Fast halo position update using scroll offset detection.

    This endpoint is optimized for quick position updates when user scrolls:
    1. Compares current screenshot with stored reference image
    2. Detects scroll offset using template matching (~10-50ms)
    3. Applies offset to known bounding box

    Much faster than OCR-based detection (~10-50ms vs ~500-2000ms).
    Falls back to storing reference if no previous reference exists.

    The reference image is stored after each full CV analysis.
    """
    import time
    import base64
    import cv2
    import numpy as np

    from cv_pipeline.scroll_detector import get_scroll_detector, apply_scroll_offset_to_bbox
    from app.services.reference_store import get_reference_store

    start_time = time.time()

    # Use session_id if provided, otherwise use target_label as fallback key
    reference_key = request.session_id or f"label:{request.target_label}"

    logger.info(f"[SCROLL_DETECT] Request: session_id={request.session_id}, has_bbox={request.current_bbox is not None}, ref_key={reference_key}")

    if not request.current_bbox:
        # No current bbox - we need full CV first to establish position
        # Store this image as reference for future comparisons
        reference_store = get_reference_store()
        reference_store.set_reference(
            session_id=reference_key,
            image_base64=request.image_base64,
            bbox=None,
            target_label=request.target_label,
        )

        return FastPositionUpdateResponse(
            success=True,
            found=False,
            new_bbox=None,
            confidence=0.0,
            scroll_offset_y=0,
            detection_method="none",
            processing_time_ms=0.0,
            total_time_ms=(time.time() - start_time) * 1000,
            message="No current bbox - need full CV to establish position. Reference stored.",
            reference_stored=True,
        )

    try:
        # Get reference store
        reference_store = get_reference_store()
        reference = reference_store.get_reference(reference_key)

        # Decode current image
        image_data = base64.b64decode(request.image_base64)
        np_arr = np.frombuffer(image_data, np.uint8)
        current_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if current_image is None:
            return FastPositionUpdateResponse(
                success=False,
                found=False,
                new_bbox=None,
                confidence=0.0,
                scroll_offset_y=0,
                detection_method="none",
                processing_time_ms=0.0,
                total_time_ms=(time.time() - start_time) * 1000,
                message="Failed to decode current image",
                reference_stored=False,
            )

        # If no reference exists, store current and return
        if reference is None:
            reference_store.set_reference(
                session_id=reference_key,
                image_base64=request.image_base64,
                bbox={
                    'x1': request.current_bbox.x1,
                    'y1': request.current_bbox.y1,
                    'x2': request.current_bbox.x2,
                    'y2': request.current_bbox.y2,
                },
                target_label=request.target_label,
            )

            logger.info(f"[SCROLL_DETECT] No reference for {reference_key}, stored current image")

            return FastPositionUpdateResponse(
                success=True,
                found=True,
                new_bbox=request.current_bbox,  # Return same bbox
                confidence=1.0,
                scroll_offset_y=0,
                detection_method="none",
                processing_time_ms=0.0,
                total_time_ms=(time.time() - start_time) * 1000,
                message="Reference stored. Position unchanged.",
                reference_stored=True,
            )

        # Try scroll offset detection
        scroll_detector = get_scroll_detector()
        detect_start = time.time()

        scroll_result = scroll_detector.detect_scroll_offset(
            reference_image=reference.image,
            current_image=current_image,
        )

        detect_time = (time.time() - detect_start) * 1000
        logger.info(
            f"[SCROLL_DETECT] Offset detection: {scroll_result.scroll_offset_y}px, "
            f"confidence: {scroll_result.confidence:.2f}, time: {detect_time:.0f}ms"
        )

        if scroll_result.success:
            # Apply scroll offset to current bbox
            current_bbox_dict = {
                'x1': request.current_bbox.x1,
                'y1': request.current_bbox.y1,
                'x2': request.current_bbox.x2,
                'y2': request.current_bbox.y2,
            }

            new_bbox_dict, is_visible = apply_scroll_offset_to_bbox(
                bbox=current_bbox_dict,
                scroll_offset_y=scroll_result.scroll_offset_y,
                scroll_offset_x=scroll_result.scroll_offset_x,
                image_height=current_image.shape[0],
                image_width=current_image.shape[1],
            )

            # IMPORTANT: Only update reference image when actual scroll is detected
            # If scroll_offset is 0, keep the current reference to detect future scrolls
            # This prevents the reference from being prematurely updated by minor screen changes
            if scroll_result.scroll_offset_y != 0 or scroll_result.scroll_offset_x != 0:
                reference_store.update_reference_image(reference_key, request.image_base64)
                logger.info(f"[SCROLL_DETECT] Reference updated after scroll offset: {scroll_result.scroll_offset_y}px")

            if is_visible and new_bbox_dict:
                new_bbox = BoundingBox(
                    x1=int(new_bbox_dict['x1']),
                    y1=int(new_bbox_dict['y1']),
                    x2=int(new_bbox_dict['x2']),
                    y2=int(new_bbox_dict['y2']),
                )

                # Also update the stored bbox
                reference_store.update_bbox(reference_key, new_bbox_dict)

                total_time = (time.time() - start_time) * 1000
                logger.info(
                    f"[SCROLL_DETECT] Success: scroll={scroll_result.scroll_offset_y}px, "
                    f"new_y={new_bbox.y1}, total_time={total_time:.0f}ms"
                )

                return FastPositionUpdateResponse(
                    success=True,
                    found=True,
                    new_bbox=new_bbox,
                    confidence=scroll_result.confidence,
                    scroll_offset_y=scroll_result.scroll_offset_y,
                    detection_method="scroll_offset",
                    processing_time_ms=detect_time,
                    total_time_ms=total_time,
                    message=f"Scroll detected: {scroll_result.scroll_offset_y}px",
                    reference_stored=True,
                )
            else:
                # Element scrolled off screen
                total_time = (time.time() - start_time) * 1000
                logger.info(f"[SCROLL_DETECT] Element scrolled off screen")

                return FastPositionUpdateResponse(
                    success=True,
                    found=False,
                    new_bbox=None,
                    confidence=scroll_result.confidence,
                    scroll_offset_y=scroll_result.scroll_offset_y,
                    detection_method="scroll_offset",
                    processing_time_ms=detect_time,
                    total_time_ms=total_time,
                    message="Element scrolled off screen",
                    reference_stored=True,
                )

        else:
            # Scroll detection failed - content likely changed significantly
            # Store new reference for future comparisons
            reference_store.set_reference(
                session_id=reference_key,
                image_base64=request.image_base64,
                bbox={
                    'x1': request.current_bbox.x1,
                    'y1': request.current_bbox.y1,
                    'x2': request.current_bbox.x2,
                    'y2': request.current_bbox.y2,
                },
                target_label=request.target_label,
            )

            total_time = (time.time() - start_time) * 1000
            logger.info(
                f"[SCROLL_DETECT] Detection failed ({scroll_result.message}), "
                f"stored new reference. Needs full CV."
            )

            return FastPositionUpdateResponse(
                success=True,
                found=False,
                new_bbox=None,
                confidence=scroll_result.confidence,
                scroll_offset_y=0,
                detection_method="none",
                processing_time_ms=detect_time,
                total_time_ms=total_time,
                message=f"Content changed significantly. {scroll_result.message}. New reference stored.",
                reference_stored=True,
            )

    except Exception as e:
        logger.error(f"[SCROLL_DETECT] Error: {e}", exc_info=True)
        return FastPositionUpdateResponse(
            success=False,
            found=False,
            new_bbox=None,
            confidence=0.0,
            scroll_offset_y=0,
            detection_method="none",
            processing_time_ms=0.0,
            total_time_ms=(time.time() - start_time) * 1000,
            message=f"Position update failed: {str(e)}",
            reference_stored=False,
        )


# =============================================
# Browser URL Detection (Python-based)
# =============================================

from pydantic import BaseModel, Field


class BrowserUrlRequest(BaseModel):
    """Request to find browser with matching URL patterns."""
    url_patterns: List[str] = Field(..., description="URL patterns to match (e.g., ['rs-online.com'])")


class BrowserInfo(BaseModel):
    """Information about a browser window."""
    hwnd: int = Field(..., description="Window handle")
    title: str = Field(..., description="Window title")
    process_name: str = Field(..., description="Process name (e.g., msedge.exe)")
    url: Optional[str] = Field(None, description="Extracted URL from address bar")
    domain: Optional[str] = Field(None, description="Domain extracted from URL")


class BrowserUrlResponse(BaseModel):
    """Response from browser URL detection."""
    success: bool = True
    found: bool = False
    browser: Optional[BrowserInfo] = None
    matched_pattern: Optional[str] = None
    all_browsers: List[BrowserInfo] = Field(default_factory=list)
    message: str = ""
    detection_time_ms: float = 0.0


@router.post("/detect-browser", response_model=BrowserUrlResponse)
async def detect_browser_with_url(
    request: BrowserUrlRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Detect a browser window matching the given URL patterns.

    This uses Python's pywinauto library to extract URLs from browser
    address bars via Windows UI Automation. More reliable than the
    Rust-based implementation.

    The endpoint searches all open browser windows and returns the first
    one whose URL matches any of the provided patterns.
    """
    import time

    start_time = time.time()

    try:
        from cv_pipeline.browser_url_extractor import (
            find_browser_with_url_pattern,
            find_all_browser_windows,
            get_browser_url_pywinauto,
            url_matches_pattern,
        )

        logger.info(f"[BROWSER_DETECT] Searching for URL patterns: {request.url_patterns}")

        # Find all browsers first (for debugging/listing)
        all_browsers_raw = find_all_browser_windows()
        all_browsers = []

        for b in all_browsers_raw:
            # Extract URL for each browser
            url = get_browser_url_pywinauto(b["hwnd"])
            browser_info = BrowserInfo(
                hwnd=b["hwnd"],
                title=b["title"],
                process_name=b["process_name"],
                url=url,
                domain=None,
            )
            if url:
                from cv_pipeline.browser_url_extractor import extract_domain
                browser_info.domain = extract_domain(url)
            all_browsers.append(browser_info)

        detection_time = (time.time() - start_time) * 1000

        # Try to find a matching browser
        result = find_browser_with_url_pattern(request.url_patterns)

        if result:
            matched_browser = BrowserInfo(
                hwnd=result["hwnd"],
                title=result["title"],
                process_name=result["process_name"],
                url=result.get("url"),
                domain=result.get("domain"),
            )

            # Find which pattern matched
            matched_pattern = None
            if result.get("url"):
                for pattern in request.url_patterns:
                    if url_matches_pattern(result["url"], pattern):
                        matched_pattern = pattern
                        break

            logger.info(f"[BROWSER_DETECT] Found matching browser: {result['title'][:50]}...")

            return BrowserUrlResponse(
                success=True,
                found=True,
                browser=matched_browser,
                matched_pattern=matched_pattern,
                all_browsers=all_browsers,
                message=f"Found browser matching URL pattern",
                detection_time_ms=detection_time,
            )

        logger.info(f"[BROWSER_DETECT] No browser found matching patterns. {len(all_browsers)} browsers checked.")

        return BrowserUrlResponse(
            success=True,
            found=False,
            browser=None,
            matched_pattern=None,
            all_browsers=all_browsers,
            message=f"No browser found matching URL patterns. {len(all_browsers)} browsers checked.",
            detection_time_ms=detection_time,
        )

    except ImportError as e:
        logger.error(f"[BROWSER_DETECT] pywinauto not available: {e}")
        return BrowserUrlResponse(
            success=False,
            found=False,
            browser=None,
            matched_pattern=None,
            all_browsers=[],
            message=f"Browser detection not available: pywinauto not installed",
            detection_time_ms=(time.time() - start_time) * 1000,
        )
    except Exception as e:
        logger.error(f"[BROWSER_DETECT] Error: {e}", exc_info=True)
        return BrowserUrlResponse(
            success=False,
            found=False,
            browser=None,
            matched_pattern=None,
            all_browsers=[],
            message=f"Browser detection failed: {str(e)}",
            detection_time_ms=(time.time() - start_time) * 1000,
        )
