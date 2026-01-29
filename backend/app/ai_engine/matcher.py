"""
Element Matcher

Matches detected UI elements to instruction targets using:
- Label/text similarity
- Element type compatibility
- Spatial proximity
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from difflib import SequenceMatcher
import re
import logging

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class UIElement:
    """Detected UI element from CV pipeline."""
    element_id: str
    type: str
    label: Optional[str]
    bbox: Dict[str, int]  # {x1, y1, x2, y2}
    confidence: float
    metadata: Dict[str, Any]


@dataclass
class MatchResult:
    """Result of element matching."""
    element: UIElement
    confidence: float
    match_reasons: List[str]


@dataclass
class TargetSpec:
    """Specification for target element to find."""
    element_type: Optional[str] = None  # e.g., "button", "input", "link"
    label: Optional[str] = None  # e.g., "Submit", "Search..."
    keywords: Optional[List[str]] = None  # e.g., ["create", "new", "issue"]
    action: Optional[str] = None  # e.g., "click", "type"


class ElementMatcher:
    """
    Matches UI elements to instruction targets.

    Uses multiple signals:
    1. Label similarity (fuzzy string matching)
    2. Type compatibility (button for click, input for type, etc.)
    3. Keyword presence in label/metadata
    """

    # Element type compatibility matrix
    # Note: "interactive_element" is a generic type from OmniParser, compatible with all actions
    # Note: "icon" is added to all actions since OmniParser often detects UI elements as icons
    TYPE_COMPATIBILITY = {
        "click": ["button", "link", "icon", "tab", "checkbox", "radio", "menu", "menuitem", "interactive_element"],
        "type": ["input", "textfield", "textarea", "searchbox", "combobox", "interactive_element", "icon"],
        "select": ["dropdown", "select", "combobox", "listbox", "menu", "interactive_element", "icon"],
        "scroll": ["scrollbar", "list", "table", "container", "interactive_element", "icon"],
        "hover": ["button", "link", "icon", "tooltip", "menu", "interactive_element"],
    }

    # Type aliases for normalization
    TYPE_ALIASES = {
        "btn": "button",
        "img": "icon",
        "image": "icon",
        "text": "label",
        "txt": "input",
        "textbox": "input",
        "anchor": "link",
        "a": "link",
    }

    def __init__(self, match_threshold: Optional[float] = None):
        """
        Initialize element matcher.

        Args:
            match_threshold: Minimum confidence for valid match (defaults to settings)
        """
        self.match_threshold = match_threshold or settings.GUIDANCE_MATCH_THRESHOLD

    def normalize_type(self, element_type: str) -> str:
        """Normalize element type to standard form."""
        normalized = element_type.lower().strip()
        return self.TYPE_ALIASES.get(normalized, normalized)

    def calculate_label_similarity(
        self,
        target_label: str,
        element_label: Optional[str]
    ) -> float:
        """
        Calculate similarity between target and element labels.

        Uses multiple matching strategies:
        1. Exact match
        2. Containment (target in element or vice versa)
        3. Word overlap (for multi-word labels)
        4. Fuzzy match using SequenceMatcher

        Args:
            target_label: Target label to match
            element_label: Element's label (may be None)

        Returns:
            Similarity score 0.0 - 1.0
        """
        if not element_label:
            return 0.0

        # Normalize both labels
        target = target_label.lower().strip()
        element = element_label.lower().strip()

        # Exact match
        if target == element:
            return 1.0

        # Check if target is contained in element (or vice versa)
        # But require minimum length to avoid single-character false positives
        # e.g., "C" should not match "Create a password" just because "c" is in "create"
        min_containment_length = 3
        if len(element) >= min_containment_length and len(target) >= min_containment_length:
            if target in element or element in target:
                return 0.9

        # Word overlap matching (useful for OCR-enriched labels)
        # E.g., "Create a password" matches "Password" or "password"
        target_words = set(re.findall(r'\w+', target))
        element_words = set(re.findall(r'\w+', element))

        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'to', 'in', 'on', 'at', 'for', 'and', 'or', 'your', 'click', 'press', 'enter', 'type'}
        target_words = target_words - stop_words
        element_words = element_words - stop_words

        if target_words and element_words:
            # Check for any word overlap
            common_words = target_words & element_words
            if common_words:
                # Calculate overlap ratio - use target words as the denominator
                # This ensures the target's words are found in the element
                overlap_ratio = len(common_words) / len(target_words)

                # Require higher overlap for high scores to avoid false positives
                # e.g., "Parcel Tracking" vs "[Your Order Number/Tracking" only shares 1/2 words
                if overlap_ratio >= 0.9:  # Nearly all target words match
                    return 0.85
                elif overlap_ratio >= 0.75:  # Most target words match
                    return 0.75
                elif overlap_ratio >= 0.5:  # At least half target words match
                    return 0.6 + (0.15 * overlap_ratio)  # Max 0.675 for 50% match
                elif overlap_ratio > 0:  # Some words match
                    return 0.4 + (0.2 * overlap_ratio)  # Max 0.5 for <50% match

        # Fuzzy match using SequenceMatcher
        return SequenceMatcher(None, target, element).ratio()

    def check_type_compatibility(
        self,
        action: Optional[str],
        element_type: str
    ) -> Tuple[bool, float]:
        """
        Check if element type is compatible with action.

        Args:
            action: Action type (click, type, etc.)
            element_type: Detected element type

        Returns:
            Tuple of (is_compatible, confidence_boost)
        """
        if not action:
            return True, 0.0

        normalized_type = self.normalize_type(element_type)
        compatible_types = self.TYPE_COMPATIBILITY.get(action.lower(), [])

        if normalized_type in compatible_types:
            return True, 0.1  # Boost confidence by 10%

        # Partial match (element type contains compatible type)
        for compatible in compatible_types:
            if compatible in normalized_type or normalized_type in compatible:
                return True, 0.05

        return False, -0.2  # Penalty for incompatible type

    def check_keywords(
        self,
        keywords: List[str],
        element: UIElement
    ) -> Tuple[int, float]:
        """
        Check how many keywords match the element.

        Args:
            keywords: List of keywords to search for
            element: UI element to check

        Returns:
            Tuple of (matches_count, confidence_boost)
        """
        if not keywords:
            return 0, 0.0

        matches = 0
        search_text = ""

        # Combine all searchable text
        if element.label:
            search_text += element.label.lower() + " "
        if element.metadata:
            for key in ["text", "aria-label", "title", "placeholder"]:
                if key in element.metadata:
                    search_text += str(element.metadata[key]).lower() + " "

        for keyword in keywords:
            if keyword.lower() in search_text:
                matches += 1

        # Calculate boost based on keyword matches
        if not keywords:
            return 0, 0.0

        match_ratio = matches / len(keywords)
        boost = match_ratio * 0.4  # Up to 40% boost for all keywords (increased from 20%)

        return matches, boost

    def match_element(
        self,
        target: TargetSpec,
        elements: List[UIElement]
    ) -> Optional[MatchResult]:
        """
        Find the best matching element for a target specification.

        Args:
            target: Target specification to match
            elements: List of detected UI elements

        Returns:
            Best matching element with confidence, or None if no match
        """
        if not elements:
            return None

        candidates: List[Tuple[UIElement, float, List[str]]] = []

        for element in elements:
            confidence = 0.0
            reasons = []
            label_sim = 0.0
            keyword_matches = 0

            # 1. Label similarity
            if target.label:
                label_sim = self.calculate_label_similarity(
                    target.label, element.label
                )
                confidence += label_sim * 0.5  # Label is 50% of score
                if label_sim > 0.7:
                    reasons.append(f"Label match: {label_sim:.0%}")

            # 2. Type compatibility
            if target.element_type or target.action:
                check_type = target.element_type or ""
                is_compat, type_boost = self.check_type_compatibility(
                    target.action, element.type
                )
                confidence += type_boost

                # Direct type match
                if target.element_type:
                    if self.normalize_type(element.type) == self.normalize_type(target.element_type):
                        confidence += 0.2
                        reasons.append(f"Type match: {element.type}")

                if is_compat and target.action:
                    reasons.append(f"Compatible with action: {target.action}")

            # 3. Keyword matching - give higher weight when label similarity is low
            if target.keywords:
                keyword_matches, keyword_boost = self.check_keywords(
                    target.keywords, element
                )
                # If label similarity is low, boost keyword importance
                if target.label and label_sim < 0.5:
                    keyword_boost *= 2  # Double keyword weight when label doesn't match well
                confidence += keyword_boost
                if keyword_matches > 0:
                    reasons.append(f"Keywords found: {keyword_matches}/{len(target.keywords)}")

            # 4. Element detection confidence as tiebreaker
            confidence += element.confidence * 0.1  # 10% from detection confidence

            # Normalize confidence to 0-1 range
            confidence = min(max(confidence, 0.0), 1.0)

            # Only add as candidate if:
            # 1. Overall confidence is above threshold AND
            # 2. Label similarity is reasonable (at least 0.5) OR there's a keyword match
            label_sim_ok = target.label and label_sim >= 0.5
            has_keyword_match = target.keywords and keyword_matches > 0

            # Debug output for matching
            if element.label and confidence >= 0.3:
                print(f"[MATCHER] Evaluating '{element.label}': label_sim={label_sim:.2f}, conf={confidence:.2f}, label_ok={label_sim_ok}, kw_match={has_keyword_match}")

            if confidence >= self.match_threshold and (label_sim_ok or has_keyword_match or not target.label):
                candidates.append((element, confidence, reasons))

        if not candidates:
            logger.debug(f"No matching element found for target: {target}")
            print(f"[MATCHER] No candidates above threshold {self.match_threshold} for target label: '{target.label}'")
            # Show top 5 elements by label similarity for debugging
            if target.label:
                scored = []
                for elem in elements:
                    if elem.label:
                        sim = self.calculate_label_similarity(target.label, elem.label)
                        scored.append((elem.label, sim))
                scored.sort(key=lambda x: x[1], reverse=True)
                print(f"[MATCHER] Top 5 closest labels: {scored[:5]}")
            return None

        # Sort by confidence and return best match
        candidates.sort(key=lambda x: x[1], reverse=True)
        best = candidates[0]

        logger.info(
            f"Matched element '{best[0].label}' (type={best[0].type}) "
            f"with confidence {best[1]:.2f}"
        )

        return MatchResult(
            element=best[0],
            confidence=best[1],
            match_reasons=best[2]
        )

    def match_multiple(
        self,
        targets: List[TargetSpec],
        elements: List[UIElement]
    ) -> List[Optional[MatchResult]]:
        """
        Match multiple targets to elements.

        Args:
            targets: List of target specifications
            elements: List of detected UI elements

        Returns:
            List of match results (None for unmatched targets)
        """
        return [self.match_element(target, elements) for target in targets]

    def find_by_label(
        self,
        label: str,
        elements: List[UIElement],
        element_type: Optional[str] = None
    ) -> Optional[MatchResult]:
        """
        Convenience method to find element by label.

        Args:
            label: Label to search for
            elements: List of detected UI elements
            element_type: Optional type filter

        Returns:
            Matching element or None
        """
        target = TargetSpec(
            label=label,
            element_type=element_type
        )
        return self.match_element(target, elements)

    def find_for_action(
        self,
        action: str,
        label: str,
        elements: List[UIElement],
        keywords: Optional[List[str]] = None
    ) -> Optional[MatchResult]:
        """
        Find element suitable for a specific action.

        Args:
            action: Action to perform (click, type, etc.)
            label: Target label
            elements: List of detected UI elements
            keywords: Optional keywords to match

        Returns:
            Matching element or None
        """
        target = TargetSpec(
            action=action,
            label=label,
            keywords=keywords
        )
        return self.match_element(target, elements)
