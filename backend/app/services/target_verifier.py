"""
Target Application Verifier Service

Verifies if a screenshot is from the target application by checking
for brand keywords in OCR text. This is the visual verification approach
that works reliably regardless of window detection limitations.

The verification happens on the SAME screenshot used for CV analysis,
so there's no duplicate capture overhead.
"""

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of target application verification."""
    is_verified: bool
    matched_keywords: List[str]
    confidence: float
    verification_time_ms: float
    hwnd: Optional[int] = None  # Window handle for caching


class HWNDCache:
    """
    Cache of verified window handles.

    Once a window is verified visually, we cache its HWND so subsequent
    checks can skip OCR verification if the same window is still active.
    """

    def __init__(self, max_size: int = 10, expiry_seconds: float = 300):
        """
        Initialize HWND cache.

        Args:
            max_size: Maximum number of HWNDs to cache
            expiry_seconds: How long to cache a verified HWND
        """
        self._cache: Dict[int, float] = {}  # hwnd -> timestamp
        self._max_size = max_size
        self._expiry_seconds = expiry_seconds

    def is_verified(self, hwnd: int) -> bool:
        """Check if HWND is in cache and not expired."""
        if hwnd not in self._cache:
            return False

        timestamp = self._cache[hwnd]
        if time.time() - timestamp > self._expiry_seconds:
            # Expired, remove from cache
            del self._cache[hwnd]
            return False

        return True

    def mark_verified(self, hwnd: int) -> None:
        """Add HWND to cache as verified."""
        # Evict oldest if at max size
        if len(self._cache) >= self._max_size:
            oldest_hwnd = min(self._cache, key=self._cache.get)
            del self._cache[oldest_hwnd]

        self._cache[hwnd] = time.time()
        logger.info(f"[HWND Cache] Marked HWND {hwnd} as verified (cache size: {len(self._cache)})")

    def invalidate(self, hwnd: int) -> None:
        """Remove HWND from cache."""
        if hwnd in self._cache:
            del self._cache[hwnd]
            logger.info(f"[HWND Cache] Invalidated HWND {hwnd}")

    def clear(self) -> None:
        """Clear entire cache."""
        self._cache.clear()
        logger.info("[HWND Cache] Cleared all entries")


# Global HWND cache instance
_hwnd_cache = HWNDCache()


def get_hwnd_cache() -> HWNDCache:
    """Get the global HWND cache instance."""
    return _hwnd_cache


class TargetVerifier:
    """
    Verifies if a screenshot is from the target application.

    Uses OCR text extraction to check for brand keywords.
    This approach works reliably regardless of window detection limitations.
    """

    def __init__(self, hwnd_cache: Optional[HWNDCache] = None):
        """
        Initialize the target verifier.

        Args:
            hwnd_cache: Optional HWND cache instance
        """
        self.hwnd_cache = hwnd_cache or get_hwnd_cache()

    def verify_by_keywords(
        self,
        text_regions: List[Dict],
        brand_keywords: List[str],
        hwnd: Optional[int] = None,
    ) -> VerificationResult:
        """
        Verify if the OCR text contains brand keywords.

        This is called AFTER OCR is already done for the CV analysis,
        so it just checks the existing text - no duplicate processing.

        Args:
            text_regions: List of OCR text regions from CV analysis
            brand_keywords: List of brand keywords to search for
            hwnd: Optional window handle for caching

        Returns:
            VerificationResult with match info
        """
        start_time = time.perf_counter()

        # Quick cache check
        if hwnd is not None and self.hwnd_cache.is_verified(hwnd):
            logger.info(f"[TargetVerifier] HWND {hwnd} is cached as verified")
            return VerificationResult(
                is_verified=True,
                matched_keywords=["(cached)"],
                confidence=1.0,
                verification_time_ms=0.0,
                hwnd=hwnd,
            )

        if not brand_keywords:
            logger.warning("[TargetVerifier] No brand keywords configured")
            return VerificationResult(
                is_verified=True,  # No keywords = no verification needed
                matched_keywords=[],
                confidence=0.0,
                verification_time_ms=0.0,
                hwnd=hwnd,
            )

        if not text_regions:
            logger.warning("[TargetVerifier] No OCR text regions to check")
            return VerificationResult(
                is_verified=False,
                matched_keywords=[],
                confidence=0.0,
                verification_time_ms=(time.perf_counter() - start_time) * 1000,
                hwnd=hwnd,
            )

        # Collect all text for searching
        all_text_lower = " ".join(
            region.get("text", "") if isinstance(region, dict) else getattr(region, "text", "")
            for region in text_regions
        ).lower()

        # Check for keyword matches
        matched_keywords = []
        keywords_lower = [kw.lower() for kw in brand_keywords]

        for i, keyword in enumerate(keywords_lower):
            if keyword in all_text_lower:
                matched_keywords.append(brand_keywords[i])  # Use original case

        verification_time = (time.perf_counter() - start_time) * 1000

        # Calculate confidence based on match ratio
        if matched_keywords:
            confidence = len(matched_keywords) / len(brand_keywords)
            is_verified = True

            # Cache the verified HWND
            if hwnd is not None:
                self.hwnd_cache.mark_verified(hwnd)

            logger.info(
                f"[TargetVerifier] Verified! Matched keywords: {matched_keywords} "
                f"(confidence: {confidence:.2f}, time: {verification_time:.1f}ms)"
            )
        else:
            confidence = 0.0
            is_verified = False
            logger.info(
                f"[TargetVerifier] Not verified. Looking for: {brand_keywords}, "
                f"found text length: {len(all_text_lower)} chars"
            )

        return VerificationResult(
            is_verified=is_verified,
            matched_keywords=matched_keywords,
            confidence=confidence,
            verification_time_ms=verification_time,
            hwnd=hwnd,
        )

    def verify_from_screen_state(
        self,
        screen_state: Dict,
        brand_keywords: List[str],
        hwnd: Optional[int] = None,
    ) -> VerificationResult:
        """
        Verify using a complete screen state from CV analysis.

        Args:
            screen_state: Screen state dict from CV analysis
            brand_keywords: List of brand keywords to search for
            hwnd: Optional window handle for caching

        Returns:
            VerificationResult with match info
        """
        text_regions = screen_state.get("text_regions", [])
        return self.verify_by_keywords(text_regions, brand_keywords, hwnd)


# Singleton instance
_verifier_instance: Optional[TargetVerifier] = None


def get_target_verifier() -> TargetVerifier:
    """Get the singleton target verifier instance."""
    global _verifier_instance
    if _verifier_instance is None:
        _verifier_instance = TargetVerifier()
    return _verifier_instance
