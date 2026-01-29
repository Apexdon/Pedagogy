"""
Perceptual Hash Cache for Verified Pages

Maintains a cache of perceptual hashes for verified target app pages.
When the user navigates between pages on the target app, we can skip OCR
verification if we've already verified that specific page visually.

This dramatically speeds up verification when:
- User navigates between different pages of the same app
- User returns to a previously visited page
- User scrolls (minor changes don't affect perceptual hash)

The cache is per-session and clears when:
- User leaves the target app
- Session ends
- Cache reaches max size (LRU eviction)
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Tuple
from io import BytesIO
import base64

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Lazy load imagehash to avoid import errors if not installed
_imagehash_available: Optional[bool] = None


def _check_imagehash_available() -> bool:
    """Check if imagehash library is available."""
    global _imagehash_available

    if _imagehash_available is not None:
        return _imagehash_available

    try:
        import imagehash
        _imagehash_available = True
        logger.info("[PageHashCache] imagehash library available")
        return True
    except ImportError:
        logger.warning("[PageHashCache] imagehash not installed, perceptual hashing disabled")
        _imagehash_available = False
        return False


@dataclass
class PageHashEntry:
    """Entry in the page hash cache."""
    hash_value: str  # String representation of perceptual hash
    timestamp: float  # When this hash was verified
    verification_count: int = 1  # How many times this page was visited


@dataclass
class PageHashCache:
    """
    Cache of perceptual hashes for verified target app pages.

    Uses perceptual hashing (pHash) which is robust to:
    - Minor pixel changes (cursor, clock, animations)
    - Small layout shifts
    - Compression artifacts

    But detects significant changes like:
    - Page navigation
    - Content loading
    - Major UI state changes
    """

    max_size: int = 50  # Maximum number of page hashes to cache
    hash_threshold: int = 10  # Max Hamming distance to consider a match (0-64 scale)
    expiry_seconds: float = 600  # 10 minute expiry for individual hashes

    # Internal state
    _cache: Dict[str, PageHashEntry] = field(default_factory=dict)
    _access_order: list = field(default_factory=list)  # For LRU eviction

    def compute_hash(self, image: np.ndarray) -> Optional[str]:
        """
        Compute perceptual hash for an image.

        Args:
            image: BGR or RGB numpy array

        Returns:
            String representation of perceptual hash, or None if hashing fails
        """
        if not _check_imagehash_available():
            return None

        import imagehash

        try:
            # Convert numpy array to PIL Image
            if len(image.shape) == 3 and image.shape[2] == 3:
                # Assume BGR from OpenCV, convert to RGB
                pil_image = Image.fromarray(image[:, :, ::-1])
            else:
                pil_image = Image.fromarray(image)

            # Resize to standard size for consistent hashing
            # Use header region (top portion) for faster, more stable hashing
            width, height = pil_image.size
            header_height = min(250, height // 3)  # Top 1/3 or 250px, whichever is smaller
            pil_image = pil_image.crop((0, 0, width, header_height))

            # Compute perceptual hash (pHash)
            # pHash is more robust to minor changes than average hash
            hash_value = imagehash.phash(pil_image, hash_size=16)  # 256-bit hash

            return str(hash_value)

        except Exception as e:
            logger.error(f"[PageHashCache] Error computing hash: {e}")
            return None

    def compute_hash_from_base64(self, image_base64: str) -> Optional[str]:
        """
        Compute perceptual hash from base64-encoded image.

        Args:
            image_base64: Base64-encoded image string

        Returns:
            String representation of perceptual hash, or None if hashing fails
        """
        if not _check_imagehash_available():
            return None

        import imagehash

        try:
            # Decode base64 to image
            image_bytes = base64.b64decode(image_base64)
            pil_image = Image.open(BytesIO(image_bytes))

            # Use header region for hashing
            width, height = pil_image.size
            header_height = min(250, height // 3)
            pil_image = pil_image.crop((0, 0, width, header_height))

            # Compute perceptual hash
            hash_value = imagehash.phash(pil_image, hash_size=16)

            return str(hash_value)

        except Exception as e:
            logger.error(f"[PageHashCache] Error computing hash from base64: {e}")
            return None

    def _hash_distance(self, hash1: str, hash2: str) -> int:
        """
        Compute Hamming distance between two perceptual hashes.

        Args:
            hash1: First hash string
            hash2: Second hash string

        Returns:
            Hamming distance (0 = identical, higher = more different)
        """
        if not _check_imagehash_available():
            return 999  # Return high distance if imagehash not available

        import imagehash

        try:
            h1 = imagehash.hex_to_hash(hash1)
            h2 = imagehash.hex_to_hash(hash2)
            return h1 - h2  # Hamming distance
        except Exception as e:
            logger.error(f"[PageHashCache] Error computing hash distance: {e}")
            return 999

    def is_verified_page(self, image_hash: str) -> Tuple[bool, Optional[str]]:
        """
        Check if an image hash matches any verified page.

        Args:
            image_hash: Perceptual hash of current image

        Returns:
            Tuple of (is_match, matched_hash or None)
        """
        if not image_hash:
            return False, None

        current_time = time.time()

        # Check against all cached hashes
        for cached_hash, entry in list(self._cache.items()):
            # Check expiry
            if current_time - entry.timestamp > self.expiry_seconds:
                self._remove_hash(cached_hash)
                continue

            # Check hash distance
            distance = self._hash_distance(image_hash, cached_hash)

            if distance <= self.hash_threshold:
                # Match found! Update access time and count
                entry.timestamp = current_time
                entry.verification_count += 1
                self._update_access_order(cached_hash)

                logger.info(
                    f"[PageHashCache] Page hash match! distance={distance}, "
                    f"visits={entry.verification_count}"
                )
                return True, cached_hash

        return False, None

    def add_verified_page(self, image_hash: str) -> None:
        """
        Add a verified page hash to the cache.

        Args:
            image_hash: Perceptual hash of verified page
        """
        if not image_hash:
            return

        # Check if already cached (or similar hash exists)
        is_match, matched_hash = self.is_verified_page(image_hash)
        if is_match:
            # Already cached, just updated in is_verified_page
            return

        # Evict oldest if at max size
        while len(self._cache) >= self.max_size:
            self._evict_oldest()

        # Add new entry
        self._cache[image_hash] = PageHashEntry(
            hash_value=image_hash,
            timestamp=time.time(),
            verification_count=1
        )
        self._access_order.append(image_hash)

        logger.info(f"[PageHashCache] Added new page hash (cache size: {len(self._cache)})")

    def _update_access_order(self, hash_value: str) -> None:
        """Update LRU access order."""
        if hash_value in self._access_order:
            self._access_order.remove(hash_value)
        self._access_order.append(hash_value)

    def _remove_hash(self, hash_value: str) -> None:
        """Remove a hash from the cache."""
        if hash_value in self._cache:
            del self._cache[hash_value]
        if hash_value in self._access_order:
            self._access_order.remove(hash_value)

    def _evict_oldest(self) -> None:
        """Evict the least recently used hash."""
        if self._access_order:
            oldest = self._access_order.pop(0)
            if oldest in self._cache:
                del self._cache[oldest]
                logger.debug(f"[PageHashCache] Evicted oldest hash")

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()
        self._access_order.clear()
        logger.info("[PageHashCache] Cache cleared")

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hash_threshold": self.hash_threshold,
            "expiry_seconds": self.expiry_seconds,
            "total_visits": sum(e.verification_count for e in self._cache.values()),
        }


# Global page hash cache instance
_page_hash_cache: Optional[PageHashCache] = None


def get_page_hash_cache() -> PageHashCache:
    """Get the global page hash cache instance."""
    global _page_hash_cache

    if _page_hash_cache is None:
        _page_hash_cache = PageHashCache(
            max_size=50,
            hash_threshold=10,  # Allow some variation
            expiry_seconds=600,  # 10 minutes
        )

    return _page_hash_cache


def clear_page_hash_cache() -> None:
    """Clear the global page hash cache."""
    global _page_hash_cache

    if _page_hash_cache is not None:
        _page_hash_cache.clear()


class FastVerificationWithHash:
    """
    Fast verification service that combines:
    1. Perceptual hash cache (instant, ~1ms)
    2. HWND cache (instant, ~1ms)
    3. Fast OCR verification (fast, ~200-400ms)

    The verification flow:
    1. Check perceptual hash cache → if match, return verified
    2. Check HWND cache → if match, return verified
    3. Run fast OCR → if verified, add hash to cache
    """

    def __init__(
        self,
        page_hash_cache: Optional[PageHashCache] = None,
    ):
        self.page_hash_cache = page_hash_cache or get_page_hash_cache()

    def quick_verify(
        self,
        image_base64: str,
        hwnd: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """
        Perform quick verification using cached hashes.

        Args:
            image_base64: Base64-encoded screenshot
            hwnd: Optional window handle

        Returns:
            Tuple of (is_verified, verification_method)
            verification_method is one of: "page_hash", "hwnd", "none"
        """
        # Step 1: Check perceptual hash cache
        image_hash = self.page_hash_cache.compute_hash_from_base64(image_base64)

        if image_hash:
            is_match, _ = self.page_hash_cache.is_verified_page(image_hash)
            if is_match:
                return True, "page_hash"

        # Step 2: HWND cache is checked separately in the main verify function
        # (handled by target_verifier.py)

        return False, "none"

    def add_verified_page(self, image_base64: str) -> None:
        """
        Add a verified page to the hash cache.

        Call this after OCR verification succeeds.

        Args:
            image_base64: Base64-encoded screenshot of verified page
        """
        image_hash = self.page_hash_cache.compute_hash_from_base64(image_base64)
        if image_hash:
            self.page_hash_cache.add_verified_page(image_hash)

    def clear_cache(self) -> None:
        """Clear the page hash cache (call when leaving target app)."""
        self.page_hash_cache.clear()

    def get_stats(self) -> Dict:
        """Get verification statistics."""
        return {
            "page_hash_cache": self.page_hash_cache.get_stats(),
        }


# Global instance
_fast_verification_instance: Optional[FastVerificationWithHash] = None


def get_fast_verification_with_hash() -> FastVerificationWithHash:
    """Get the global fast verification instance."""
    global _fast_verification_instance

    if _fast_verification_instance is None:
        _fast_verification_instance = FastVerificationWithHash()

    return _fast_verification_instance
