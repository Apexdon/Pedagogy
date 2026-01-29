"""
Step Tracker

Manages guidance session state and step progression.
Handles persistence to database and session recovery.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.guidance import (
    GuidanceSession,
    GuidanceStep,
    GuidanceCapture,
    SessionStatus,
    StepStatus,
)
from app.ai_engine.guidance_generator import GeneratedGuidance, GuidanceStepWithTarget, HaloTarget

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """Current state of a guidance session."""
    session_id: str
    status: str
    current_step: int
    total_steps: int
    query: str
    steps: List[Dict[str, Any]]
    current_target: Optional[Dict[str, Any]]


class StepTracker:
    """
    Tracks guidance session progress and state.

    Responsibilities:
    - Create and manage sessions
    - Track step progression
    - Store captures and screen states
    - Provide session recovery
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize step tracker.

        Args:
            db: Async database session
        """
        self.db = db

    async def create_session(
        self,
        user_id: str,
        org_id: str,
        guidance: GeneratedGuidance,
        kb_id: Optional[str] = None,
        application_context: Optional[str] = None,
    ) -> GuidanceSession:
        """
        Create a new guidance session from generated guidance.

        Args:
            user_id: User ID
            org_id: Organisation ID
            guidance: Generated guidance result
            kb_id: Knowledge base ID used for RAG
            application_context: Current application context

        Returns:
            Created GuidanceSession
        """
        session = GuidanceSession(
            session_id=guidance.session_id,
            user_id=user_id,
            org_id=org_id,
            query=guidance.query,
            application_context=application_context,
            status=SessionStatus.ACTIVE.value,
            current_step=1,
            total_steps=guidance.total_steps,
            kb_id=kb_id,
            rag_context=self._serialize_rag_context(guidance.rag_context),
        )

        self.db.add(session)

        # Create step records
        for step in guidance.steps:
            db_step = self._create_step_record(guidance.session_id, step)
            self.db.add(db_step)

        await self.db.commit()

        # Re-fetch with steps eagerly loaded to avoid lazy loading issues
        result = await self.db.execute(
            select(GuidanceSession)
            .options(selectinload(GuidanceSession.steps))
            .where(GuidanceSession.session_id == guidance.session_id)
        )
        session = result.scalar_one()

        logger.info(f"Created session {session.session_id} with {guidance.total_steps} steps")

        return session

    def _create_step_record(
        self,
        session_id: str,
        step: GuidanceStepWithTarget
    ) -> GuidanceStep:
        """Create database step record from guidance step."""
        return GuidanceStep(
            step_id=str(uuid.uuid4()),
            session_id=session_id,
            step_number=step.step_number,
            instruction=step.instruction,
            detailed_instruction=step.detailed_instruction,
            target_element_type=step.target.element_type if step.target else None,
            target_element_label=step.target.label if step.target else None,
            target_bbox=step.target.bbox if step.target else None,
            action_type=step.action_type,
            action_value=step.action_value,
            match_confidence=step.match_confidence,
            status=StepStatus.CURRENT.value if step.step_number == 1 else StepStatus.PENDING.value,
        )

    def _serialize_rag_context(
        self,
        rag_context: Optional[List[Dict[str, Any]]]
    ) -> Optional[Dict[str, Any]]:
        """Serialize RAG context for storage."""
        if not rag_context:
            return None
        return {"results": rag_context}

    async def get_session(
        self,
        session_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[GuidanceSession]:
        """
        Get session by ID.

        Args:
            session_id: Session ID
            user_id: Optional user ID for authorization

        Returns:
            GuidanceSession or None
        """
        query = select(GuidanceSession).options(
            selectinload(GuidanceSession.steps),
            selectinload(GuidanceSession.captures),
        ).where(GuidanceSession.session_id == session_id)

        if user_id:
            query = query.where(GuidanceSession.user_id == user_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_session_state(
        self,
        session_id: str,
    ) -> Optional[SessionState]:
        """
        Get current session state for frontend.

        Args:
            session_id: Session ID

        Returns:
            SessionState or None
        """
        session = await self.get_session(session_id)
        if not session:
            return None

        # Build step list
        steps = []
        current_target = None

        for step in sorted(session.steps, key=lambda s: s.step_number):
            step_data = {
                "step_id": step.step_id,
                "step_number": step.step_number,
                "instruction": step.instruction,
                "detailed_instruction": step.detailed_instruction,
                "action_type": step.action_type,
                "status": step.status,
            }

            # Add target if available
            if step.target_bbox:
                step_data["target"] = {
                    "bbox": step.target_bbox,
                    "element_type": step.target_element_type,
                    "label": step.target_element_label,
                }

                # Set current target for active step
                if step.status == StepStatus.CURRENT.value:
                    current_target = step_data["target"]

            steps.append(step_data)

        return SessionState(
            session_id=session.session_id,
            status=session.status,
            current_step=session.current_step,
            total_steps=session.total_steps,
            query=session.query,
            steps=steps,
            current_target=current_target,
        )

    async def advance_step(
        self,
        session_id: str,
    ) -> Optional[SessionState]:
        """
        Advance to the next step.

        Args:
            session_id: Session ID

        Returns:
            Updated SessionState or None
        """
        session = await self.get_session(session_id)
        if not session:
            return None

        # Find current step and mark complete
        for step in session.steps:
            if step.status == StepStatus.CURRENT.value:
                step.status = StepStatus.COMPLETED.value
                step.completed_at = datetime.now(timezone.utc)
                break

        # Advance to next step
        session.current_step += 1

        if session.current_step > session.total_steps:
            # All steps completed
            session.status = SessionStatus.COMPLETED.value
            session.completed_at = datetime.now(timezone.utc)
            logger.info(f"Session {session_id} completed")
        else:
            # Mark next step as current
            for step in session.steps:
                if step.step_number == session.current_step:
                    step.status = StepStatus.CURRENT.value
                    step.started_at = datetime.now(timezone.utc)
                    break

        await self.db.commit()

        return await self.get_session_state(session_id)

    async def skip_step(
        self,
        session_id: str,
    ) -> Optional[SessionState]:
        """
        Skip the current step.

        Args:
            session_id: Session ID

        Returns:
            Updated SessionState or None
        """
        session = await self.get_session(session_id)
        if not session:
            return None

        # Find current step and mark skipped
        for step in session.steps:
            if step.status == StepStatus.CURRENT.value:
                step.status = StepStatus.SKIPPED.value
                step.completed_at = datetime.now(timezone.utc)
                break

        # Advance to next step
        session.current_step += 1

        if session.current_step > session.total_steps:
            session.status = SessionStatus.COMPLETED.value
            session.completed_at = datetime.now(timezone.utc)
        else:
            for step in session.steps:
                if step.step_number == session.current_step:
                    step.status = StepStatus.CURRENT.value
                    step.started_at = datetime.now(timezone.utc)
                    break

        await self.db.commit()

        return await self.get_session_state(session_id)

    async def go_to_step(
        self,
        session_id: str,
        step_number: int,
    ) -> Optional[SessionState]:
        """
        Jump to a specific step.

        Args:
            session_id: Session ID
            step_number: Target step number

        Returns:
            Updated SessionState or None
        """
        session = await self.get_session(session_id)
        if not session:
            return None

        if step_number < 1 or step_number > session.total_steps:
            logger.warning(f"Invalid step number: {step_number}")
            return await self.get_session_state(session_id)

        # Update current step marker
        for step in session.steps:
            if step.status == StepStatus.CURRENT.value:
                # Keep as pending if going forward, mark completed if going back
                if step.step_number < step_number:
                    step.status = StepStatus.SKIPPED.value
                else:
                    step.status = StepStatus.PENDING.value

            if step.step_number == step_number:
                step.status = StepStatus.CURRENT.value
                step.started_at = datetime.now(timezone.utc)

        session.current_step = step_number
        session.status = SessionStatus.ACTIVE.value

        await self.db.commit()

        return await self.get_session_state(session_id)

    async def update_step_target(
        self,
        session_id: str,
        step_number: int,
        target: HaloTarget,
    ) -> bool:
        """
        Update a step's target element.

        Args:
            session_id: Session ID
            step_number: Step number to update
            target: New target

        Returns:
            True if successful
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        for step in session.steps:
            if step.step_number == step_number:
                step.target_element_type = target.element_type
                step.target_element_label = target.label
                step.target_bbox = target.bbox
                step.match_confidence = target.confidence
                await self.db.commit()
                return True

        return False

    async def add_capture(
        self,
        session_id: str,
        step_id: Optional[str],
        screen_state: Dict[str, Any],
        capture_type: str = "step",
        screenshot_path: Optional[str] = None,
    ) -> GuidanceCapture:
        """
        Add a screen capture to the session.

        Args:
            session_id: Session ID
            step_id: Step ID (if capture is for specific step)
            screen_state: Screen state from CV pipeline
            capture_type: Type of capture (initial, step, verification)
            screenshot_path: Path to screenshot file

        Returns:
            Created GuidanceCapture
        """
        capture = GuidanceCapture(
            capture_id=str(uuid.uuid4()),
            session_id=session_id,
            step_id=step_id,
            capture_type=capture_type,
            screenshot_path=screenshot_path,
            screen_state=screen_state,
            element_count=len(screen_state.get("elements", [])),
            text_region_count=len(screen_state.get("text_regions", [])),
            processing_time_ms=screen_state.get("processing_time_ms"),
        )

        self.db.add(capture)
        await self.db.commit()
        await self.db.refresh(capture)

        return capture

    async def pause_session(self, session_id: str) -> bool:
        """Pause an active session."""
        session = await self.get_session(session_id)
        if not session:
            return False

        session.status = SessionStatus.PAUSED.value
        await self.db.commit()
        return True

    async def resume_session(self, session_id: str) -> Optional[SessionState]:
        """Resume a paused session."""
        session = await self.get_session(session_id)
        if not session:
            return None

        session.status = SessionStatus.ACTIVE.value
        await self.db.commit()

        return await self.get_session_state(session_id)

    async def abandon_session(self, session_id: str) -> bool:
        """Abandon a session."""
        session = await self.get_session(session_id)
        if not session:
            return False

        session.status = SessionStatus.ABANDONED.value
        session.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
        return True

    async def delete_session(self, session_id: str, user_id: str) -> bool:
        """
        Delete a session and all related data.

        Args:
            session_id: Session ID to delete
            user_id: User ID for authorization

        Returns:
            True if deleted successfully
        """
        session = await self.get_session(session_id, user_id)
        if not session:
            return False

        # Delete captures first (foreign key constraint)
        for capture in session.captures:
            await self.db.delete(capture)

        # Delete steps
        for step in session.steps:
            await self.db.delete(step)

        # Delete session
        await self.db.delete(session)
        await self.db.commit()

        logger.info(f"Deleted session {session_id}")
        return True

    async def list_sessions(
        self,
        user_id: str,
        org_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[GuidanceSession]:
        """
        List sessions for a user.

        Args:
            user_id: User ID
            org_id: Optional org filter
            status: Optional status filter
            limit: Max results

        Returns:
            List of sessions
        """
        query = select(GuidanceSession).where(
            GuidanceSession.user_id == user_id
        )

        if org_id:
            query = query.where(GuidanceSession.org_id == org_id)

        if status:
            query = query.where(GuidanceSession.status == status)

        query = query.order_by(GuidanceSession.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())
