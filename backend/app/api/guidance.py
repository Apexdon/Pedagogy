"""
Guidance API Endpoints

REST API for AI-powered guidance generation and session management.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
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
    llm_model = settings.OPENAI_MODEL if llm_provider == "openai" else settings.OLLAMA_MODEL

    try:
        from app.ai_engine.llm_client import OpenAIClient, OllamaClient

        if llm_provider == "openai":
            client = OpenAIClient()
            llm_available = await client.health_check()
            fallback_client = OllamaClient()
            fallback_available = await fallback_client.health_check()
        else:
            client = OllamaClient()
            llm_available = await client.health_check()
            fallback_client = OpenAIClient()
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
