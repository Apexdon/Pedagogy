"""
Guidance Generator

Orchestrates the complete guidance pipeline:
1. RAG query for documentation context
2. LLM reasoning for step generation
3. Element matching for UI targets
4. Halo target creation for visualization
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging
import uuid

from app.ai_engine.llm_client import LLMClient, get_llm_client
from app.ai_engine.matcher import ElementMatcher, UIElement, TargetSpec, MatchResult
from app.ai_engine.reasoner import AIReasoner, GuidanceStep, GuidanceResult
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class HaloTarget:
    """Target for Halo visual highlighting overlay."""
    target_id: str
    bbox: Dict[str, int]  # {x1, y1, x2, y2}
    element_type: str
    label: Optional[str]
    step_number: int
    action_type: str
    confidence: float


@dataclass
class GuidanceStepWithTarget:
    """Guidance step with matched UI target."""
    step_number: int
    instruction: str
    detailed_instruction: Optional[str]
    action_type: str
    action_value: Optional[str]
    target: Optional[HaloTarget]
    match_confidence: float
    status: str = "pending"  # pending, current, completed, skipped


@dataclass
class GeneratedGuidance:
    """Complete guidance session output."""
    session_id: str
    query: str
    steps: List[GuidanceStepWithTarget]
    total_steps: int
    context_summary: Optional[str]
    overall_confidence: float
    rag_context: Optional[List[Dict[str, Any]]] = None


class GuidanceGenerator:
    """
    Main orchestrator for guidance generation.

    Connects:
    - RAG system for documentation retrieval
    - LLM reasoner for step generation
    - Element matcher for UI targeting
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        reasoner: Optional[AIReasoner] = None,
        matcher: Optional[ElementMatcher] = None,
    ):
        """
        Initialize guidance generator.

        Args:
            llm_client: LLM client instance
            reasoner: AI reasoner instance
            matcher: Element matcher instance
        """
        self._llm_client = llm_client
        self.reasoner = reasoner or AIReasoner(llm_client)
        self.matcher = matcher or ElementMatcher()
        self._initialized = False

    async def _ensure_initialized(self):
        """Ensure LLM client is initialized."""
        if not self._initialized:
            if self._llm_client is None:
                self._llm_client = await get_llm_client()
            self.reasoner = AIReasoner(self._llm_client)
            self._initialized = True

    def _create_halo_target(
        self,
        step: GuidanceStep,
        match: MatchResult
    ) -> HaloTarget:
        """
        Create Halo target from matched element.

        Args:
            step: Guidance step
            match: Element match result

        Returns:
            HaloTarget for visualization
        """
        return HaloTarget(
            target_id=str(uuid.uuid4()),
            bbox=match.element.bbox,
            element_type=match.element.type,
            label=match.element.label,
            step_number=step.step_number,
            action_type=step.action_type,
            confidence=match.confidence,
        )

    def _convert_screen_elements(
        self,
        screen_state: Dict[str, Any]
    ) -> List[UIElement]:
        """
        Convert screen state elements to UIElement objects.

        Args:
            screen_state: Screen state from CV pipeline

        Returns:
            List of UIElement objects
        """
        elements = []
        for elem in screen_state.get("elements", []):
            elements.append(UIElement(
                element_id=elem.get("element_id", str(uuid.uuid4())),
                type=elem.get("type", "unknown"),
                label=elem.get("label"),
                bbox=elem.get("bbox", {"x1": 0, "y1": 0, "x2": 0, "y2": 0}),
                confidence=elem.get("confidence", 0.0),
                metadata=elem.get("metadata", {}),
            ))
        return elements

    async def generate(
        self,
        query: str,
        rag_results: Optional[List[Dict[str, Any]]] = None,
        screen_state: Optional[Dict[str, Any]] = None,
        application_context: Optional[str] = None,
    ) -> GeneratedGuidance:
        """
        Generate complete guidance for a user query.

        Args:
            query: User's question
            rag_results: RAG search results from knowledge base
            screen_state: Current screen state from CV pipeline
            application_context: Current application name/context

        Returns:
            Complete guidance with matched targets
        """
        await self._ensure_initialized()

        session_id = str(uuid.uuid4())
        logger.info(f"Generating guidance for session {session_id}: {query[:50]}...")

        # Convert screen elements if available
        screen_elements_raw = None
        ui_elements = []
        if screen_state:
            screen_elements_raw = screen_state.get("elements", [])
            ui_elements = self._convert_screen_elements(screen_state)

        # Step 1: Generate guidance steps using LLM
        guidance_result = await self.reasoner.generate_guidance(
            query=query,
            rag_results=rag_results,
            screen_elements=screen_elements_raw,
            application_context=application_context,
        )

        # Step 2: Match each step to UI elements
        steps_with_targets: List[GuidanceStepWithTarget] = []
        total_confidence = 0.0

        for step in guidance_result.steps:
            # Create target spec for matching
            target_spec = TargetSpec(
                element_type=step.target_element_type,
                label=step.target_element_label,
                keywords=step.keywords,
                action=step.action_type,
            )

            # Try to match element
            match_result = None
            halo_target = None

            if ui_elements:
                match_result = self.matcher.match_element(target_spec, ui_elements)
                if match_result:
                    halo_target = self._create_halo_target(step, match_result)

            # Create step with target
            step_with_target = GuidanceStepWithTarget(
                step_number=step.step_number,
                instruction=step.instruction,
                detailed_instruction=step.detailed_instruction,
                action_type=step.action_type,
                action_value=step.action_value,
                target=halo_target,
                match_confidence=match_result.confidence if match_result else 0.0,
            )

            steps_with_targets.append(step_with_target)
            total_confidence += step_with_target.match_confidence

        # Calculate overall confidence
        num_steps = len(steps_with_targets)
        overall_confidence = (
            (total_confidence / num_steps) if num_steps > 0 else 0.0
        )

        # Combine with reasoning confidence
        overall_confidence = (
            overall_confidence * 0.5 + guidance_result.confidence * 0.5
        )

        # Mark first step as current
        if steps_with_targets:
            steps_with_targets[0].status = "current"

        result = GeneratedGuidance(
            session_id=session_id,
            query=query,
            steps=steps_with_targets,
            total_steps=num_steps,
            context_summary=guidance_result.context_summary,
            overall_confidence=overall_confidence,
            rag_context=rag_results,
        )

        logger.info(
            f"Generated guidance: {num_steps} steps, "
            f"overall confidence {overall_confidence:.2f}"
        )

        return result

    async def regenerate_step(
        self,
        step: GuidanceStepWithTarget,
        screen_state: Dict[str, Any],
        error_message: Optional[str] = None,
    ) -> GuidanceStepWithTarget:
        """
        Regenerate a step that failed to match.

        Args:
            step: Original step that failed
            screen_state: Current screen state
            error_message: Why the step failed

        Returns:
            Regenerated step with new target
        """
        await self._ensure_initialized()

        screen_elements_raw = screen_state.get("elements", [])
        ui_elements = self._convert_screen_elements(screen_state)

        # Create original guidance step for refinement
        original_step = GuidanceStep(
            step_number=step.step_number,
            instruction=step.instruction,
            detailed_instruction=step.detailed_instruction,
            target_element_type=step.target.element_type if step.target else None,
            target_element_label=step.target.label if step.target else None,
            action_type=step.action_type,
            action_value=step.action_value,
            keywords=[],
        )

        # Refine the step
        refined_step = await self.reasoner.refine_step(
            step=original_step,
            screen_elements=screen_elements_raw,
            error_message=error_message,
        )

        # Try to match again
        target_spec = TargetSpec(
            element_type=refined_step.target_element_type,
            label=refined_step.target_element_label,
            keywords=refined_step.keywords,
            action=refined_step.action_type,
        )

        match_result = self.matcher.match_element(target_spec, ui_elements)
        halo_target = None

        if match_result:
            halo_target = self._create_halo_target(refined_step, match_result)

        return GuidanceStepWithTarget(
            step_number=refined_step.step_number,
            instruction=refined_step.instruction,
            detailed_instruction=refined_step.detailed_instruction,
            action_type=refined_step.action_type,
            action_value=refined_step.action_value,
            target=halo_target,
            match_confidence=match_result.confidence if match_result else 0.0,
            status="current",
        )

    async def update_targets(
        self,
        guidance: GeneratedGuidance,
        screen_state: Dict[str, Any],
    ) -> GeneratedGuidance:
        """
        Update targets for all steps based on new screen state.

        Use after screen changes (navigation, scrolling, etc.)

        Args:
            guidance: Existing guidance
            screen_state: New screen state

        Returns:
            Updated guidance with new targets
        """
        ui_elements = self._convert_screen_elements(screen_state)

        updated_steps = []
        total_confidence = 0.0

        for step in guidance.steps:
            # Skip completed steps
            if step.status == "completed":
                updated_steps.append(step)
                total_confidence += step.match_confidence
                continue

            # Get original target info
            element_type = step.target.element_type if step.target else None
            label = step.target.label if step.target else None

            # Create target spec
            target_spec = TargetSpec(
                element_type=element_type,
                label=label,
                action=step.action_type,
            )

            # Match against new elements
            match_result = self.matcher.match_element(target_spec, ui_elements)
            halo_target = None

            if match_result:
                halo_target = HaloTarget(
                    target_id=str(uuid.uuid4()),
                    bbox=match_result.element.bbox,
                    element_type=match_result.element.type,
                    label=match_result.element.label,
                    step_number=step.step_number,
                    action_type=step.action_type,
                    confidence=match_result.confidence,
                )

            updated_step = GuidanceStepWithTarget(
                step_number=step.step_number,
                instruction=step.instruction,
                detailed_instruction=step.detailed_instruction,
                action_type=step.action_type,
                action_value=step.action_value,
                target=halo_target,
                match_confidence=match_result.confidence if match_result else 0.0,
                status=step.status,
            )

            updated_steps.append(updated_step)
            total_confidence += updated_step.match_confidence

        # Recalculate confidence
        num_steps = len(updated_steps)
        overall_confidence = (total_confidence / num_steps) if num_steps > 0 else 0.0

        return GeneratedGuidance(
            session_id=guidance.session_id,
            query=guidance.query,
            steps=updated_steps,
            total_steps=guidance.total_steps,
            context_summary=guidance.context_summary,
            overall_confidence=overall_confidence,
            rag_context=guidance.rag_context,
        )
