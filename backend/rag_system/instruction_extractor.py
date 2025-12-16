"""
Instruction Step Extractor

Extracts structured instruction steps from document text.
Useful for converting SOPs and walkthroughs into guided steps.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict, field
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class InstructionStep:
    """Represents a single instruction step."""

    step_number: int
    instruction_text: str
    step_type: str  # navigation, click, input, select, verify, wait, other
    target_element: Optional[str] = None
    target_label: Optional[str] = None
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class InstructionExtractor:
    """
    Extracts instruction steps from text content.

    Uses pattern matching to identify step types and UI elements.
    """

    # Action verb patterns for step type detection
    STEP_TYPE_PATTERNS = {
        "click": r'\b(click|press|tap|hit|select|choose|pick)\b',
        "input": r'\b(enter|type|input|fill|write|put|insert)\b',
        "navigation": r'\b(go to|navigate|open|visit|access|browse|load)\b',
        "select": r'\b(select from|choose from|pick from|dropdown|drop-down|combo)\b',
        "verify": r'\b(verify|check|confirm|ensure|make sure|validate|see)\b',
        "wait": r'\b(wait|pause|hold|delay)\b',
        "scroll": r'\b(scroll|swipe)\b',
        "hover": r'\b(hover|mouse over|point to)\b',
        "drag": r'\b(drag|move|pull)\b',
    }

    # UI element patterns
    UI_ELEMENT_PATTERNS = {
        "button": r'\b(button|btn|submit|ok|cancel|save|delete|create|add)\s*(button)?\b',
        "input": r'\b(field|input|textbox|text box|text field|entry|form field)\b',
        "dropdown": r'\b(dropdown|drop-down|select|combo box|combobox|menu|picker)\b',
        "checkbox": r'\b(checkbox|check box|tick box|toggle)\b',
        "radio": r'\b(radio button|radio|option button)\b',
        "link": r'\b(link|hyperlink|anchor)\b',
        "menu": r'\b(menu|nav|navigation|sidebar|navbar)\b',
        "tab": r'\b(tab)\b',
        "icon": r'\b(icon|image|logo|avatar)\b',
        "modal": r'\b(modal|dialog|popup|pop-up|window|overlay)\b',
        "table": r'\b(table|grid|list|row|column)\b',
    }

    # Step pattern indicators
    STEP_INDICATORS = [
        r'^\s*\d+[.)]\s+',           # 1. or 1)
        r'^\s*Step\s+\d+[.:]\s*',    # Step 1: or Step 1.
        r'^\s*[-*]\s+',              # Bullet points
        r'^\s*[a-zA-Z][.)]\s+',      # a. or a)
        r'^\s*\[\s*\d+\s*\]\s*',     # [1]
    ]

    def extract_steps(self, text: str) -> List[InstructionStep]:
        """
        Extract instruction steps from text.

        Args:
            text: Document text content

        Returns:
            List of InstructionStep objects
        """
        if not text or not text.strip():
            return []

        steps = []

        # Split into potential steps
        potential_steps = self._split_into_steps(text)

        for idx, step_text in enumerate(potential_steps, 1):
            step = self._parse_step(idx, step_text)
            if step:
                steps.append(step)

        logger.debug(f"Extracted {len(steps)} instruction steps")
        return steps

    def _split_into_steps(self, text: str) -> List[str]:
        """Split text into individual step candidates."""
        # Try numbered lists first (most reliable)
        numbered_pattern = r'(?:^|\n)\s*(\d+[.)]\s+.+?)(?=\n\s*\d+[.)]|\n\n|$)'
        numbered_matches = re.findall(numbered_pattern, text, re.DOTALL)
        if len(numbered_matches) >= 2:
            return [m.strip() for m in numbered_matches if m.strip()]

        # Try "Step N" pattern
        step_pattern = r'(?:^|\n)\s*(Step\s+\d+[.:].+?)(?=\nStep\s+\d+|\n\n|$)'
        step_matches = re.findall(step_pattern, text, re.IGNORECASE | re.DOTALL)
        if len(step_matches) >= 2:
            return [m.strip() for m in step_matches if m.strip()]

        # Try bullet points
        bullet_pattern = r'(?:^|\n)\s*([-*]\s+.+?)(?=\n\s*[-*]|\n\n|$)'
        bullet_matches = re.findall(bullet_pattern, text, re.DOTALL)
        if len(bullet_matches) >= 2:
            return [m.strip() for m in bullet_matches if m.strip()]

        # Fallback: split by sentences that contain action verbs
        sentences = self._split_into_sentences(text)
        action_sentences = []
        for sentence in sentences:
            if self._contains_action_verb(sentence) and len(sentence) > 20:
                action_sentences.append(sentence)

        if len(action_sentences) >= 2:
            return action_sentences

        # Last resort: split by paragraphs
        paragraphs = text.split('\n\n')
        return [p.strip() for p in paragraphs if p.strip() and len(p.strip()) > 30]

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _contains_action_verb(self, text: str) -> bool:
        """Check if text contains an action verb."""
        text_lower = text.lower()
        for patterns in self.STEP_TYPE_PATTERNS.values():
            if re.search(patterns, text_lower):
                return True
        return False

    def _parse_step(self, step_number: int, text: str) -> Optional[InstructionStep]:
        """Parse a single step text into an InstructionStep."""
        if not text or len(text) < 10:
            return None

        # Clean up step prefix
        clean_text = text
        for pattern in self.STEP_INDICATORS:
            clean_text = re.sub(pattern, '', clean_text, count=1)
        clean_text = clean_text.strip()

        if not clean_text or len(clean_text) < 10:
            return None

        # Detect step type
        step_type = self._detect_step_type(clean_text)

        # Extract target element
        target_element, target_label = self._extract_target(clean_text)

        return InstructionStep(
            step_number=step_number,
            instruction_text=clean_text,
            step_type=step_type,
            target_element=target_element,
            target_label=target_label
        )

    def _detect_step_type(self, text: str) -> str:
        """Detect the type of action in the step."""
        text_lower = text.lower()

        # Check each pattern in order of specificity
        for step_type, pattern in self.STEP_TYPE_PATTERNS.items():
            if re.search(pattern, text_lower):
                return step_type

        return "other"

    def _extract_target(self, text: str) -> tuple:
        """
        Extract target element type and label from step text.

        Returns:
            Tuple of (element_type, label) or (None, None)
        """
        text_lower = text.lower()

        # Detect element type
        target_element = None
        for elem_type, pattern in self.UI_ELEMENT_PATTERNS.items():
            if re.search(pattern, text_lower):
                target_element = elem_type
                break

        # Try to extract the label
        target_label = None

        # Pattern 1: Text in quotes (most reliable)
        quoted = re.findall(r'["\']([^"\']+)["\']', text)
        if quoted:
            # Take the first quoted text that looks like a label
            for q in quoted:
                if len(q) < 50:  # Labels are usually short
                    target_label = q
                    break

        # Pattern 2: "the X button/field/link" pattern
        if not target_label:
            label_patterns = [
                r'the\s+["\']?(\w+(?:\s+\w+)?)["\']?\s+(?:button|link|field|tab|menu|icon)',
                r'(?:click|press|tap)\s+(?:on\s+)?["\']?(\w+(?:\s+\w+)?)["\']?(?:\s+button)?',
                r'(?:select|choose)\s+["\']?(\w+(?:\s+\w+)?)["\']?',
            ]
            for pattern in label_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    label = match.group(1)
                    if len(label) < 30:
                        target_label = label
                        break

        return target_element, target_label


def extract_instructions(text: str) -> List[InstructionStep]:
    """
    Convenience function to extract instruction steps from text.

    Args:
        text: Document text content

    Returns:
        List of InstructionStep objects
    """
    extractor = InstructionExtractor()
    return extractor.extract_steps(text)


def instructions_to_dict(steps: List[InstructionStep]) -> List[Dict[str, Any]]:
    """
    Convert list of InstructionStep objects to list of dictionaries.

    Args:
        steps: List of InstructionStep objects

    Returns:
        List of dictionaries
    """
    return [step.to_dict() for step in steps]
