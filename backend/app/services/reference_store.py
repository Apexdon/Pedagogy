"""
Reference Image Store

Stores reference screenshots for scroll offset detection.
Each session can have a reference image that is used to detect
scroll offset when the user scrolls.
"""

import base64
import time
from dataclasses import dataclass, field
from typing import Dict, Optional
from threading import Lock

import numpy as np
import cv2


@dataclass
class ReferenceImage:
    """Stores a reference image with metadata."""
    image: np.ndarray  # BGR numpy array
    timestamp: float
    bbox: Optional[dict] = None  # Current target bbox {x1, y1, x2, y2}
    target_label: Optional[str] = None


@dataclass
class SessionReferenceStore:
    """In-memory store for reference images per session."""
    _references: Dict[str, ReferenceImage] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)
    _max_age_seconds: float = 300.0  # Auto-expire references after 5 minutes
    _max_sessions: int = 100  # Limit to prevent memory bloat

    def set_reference(
        self,
        session_id: str,
        image_base64: str,
        bbox: Optional[dict] = None,
        target_label: Optional[str] = None,
    ) -> bool:
        """
        Store a reference image for a session.

        Args:
            session_id: The guidance session ID
            image_base64: Base64 encoded image
            bbox: Current target bounding box
            target_label: Current target label

        Returns:
            True if stored successfully
        """
        try:
            # Decode base64 to numpy array
            image_data = base64.b64decode(image_base64)
            np_arr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if image is None:
                print(f"[ReferenceStore] Failed to decode image for session {session_id}")
                return False

            with self._lock:
                # Clean up old references first
                self._cleanup_expired()

                # Store new reference
                self._references[session_id] = ReferenceImage(
                    image=image,
                    timestamp=time.time(),
                    bbox=bbox,
                    target_label=target_label,
                )
                print(f"[ReferenceStore] Stored reference for session {session_id}, shape: {image.shape}")
                return True

        except Exception as e:
            print(f"[ReferenceStore] Error storing reference: {e}")
            return False

    def get_reference(self, session_id: str) -> Optional[ReferenceImage]:
        """
        Get the reference image for a session.

        Args:
            session_id: The guidance session ID

        Returns:
            ReferenceImage if found and not expired, None otherwise
        """
        with self._lock:
            ref = self._references.get(session_id)

            if ref is None:
                return None

            # Check if expired
            if time.time() - ref.timestamp > self._max_age_seconds:
                del self._references[session_id]
                return None

            return ref

    def update_bbox(
        self,
        session_id: str,
        bbox: dict,
        target_label: Optional[str] = None,
    ) -> bool:
        """
        Update the bbox for an existing reference.

        Args:
            session_id: The guidance session ID
            bbox: New bounding box
            target_label: Optional new target label

        Returns:
            True if updated successfully
        """
        with self._lock:
            ref = self._references.get(session_id)
            if ref is None:
                return False

            ref.bbox = bbox
            if target_label:
                ref.target_label = target_label
            ref.timestamp = time.time()  # Refresh timestamp
            return True

    def update_reference_image(
        self,
        session_id: str,
        image_base64: str,
    ) -> bool:
        """
        Update just the reference image (keep bbox).

        Args:
            session_id: The guidance session ID
            image_base64: New base64 encoded image

        Returns:
            True if updated successfully
        """
        try:
            image_data = base64.b64decode(image_base64)
            np_arr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if image is None:
                return False

            with self._lock:
                ref = self._references.get(session_id)
                if ref is None:
                    return False

                ref.image = image
                ref.timestamp = time.time()
                return True

        except Exception as e:
            print(f"[ReferenceStore] Error updating reference image: {e}")
            return False

    def delete_reference(self, session_id: str) -> bool:
        """Delete reference for a session."""
        with self._lock:
            if session_id in self._references:
                del self._references[session_id]
                return True
            return False

    def has_reference(self, session_id: str) -> bool:
        """Check if a valid reference exists for a session."""
        ref = self.get_reference(session_id)
        return ref is not None

    def _cleanup_expired(self) -> None:
        """Remove expired references (called within lock)."""
        current_time = time.time()
        expired = [
            sid for sid, ref in self._references.items()
            if current_time - ref.timestamp > self._max_age_seconds
        ]
        for sid in expired:
            del self._references[sid]

        # If still over limit, remove oldest
        if len(self._references) > self._max_sessions:
            sorted_refs = sorted(
                self._references.items(),
                key=lambda x: x[1].timestamp
            )
            for sid, _ in sorted_refs[:len(self._references) - self._max_sessions]:
                del self._references[sid]

    def get_stats(self) -> dict:
        """Get store statistics."""
        with self._lock:
            return {
                "total_sessions": len(self._references),
                "max_sessions": self._max_sessions,
                "max_age_seconds": self._max_age_seconds,
            }


# Global singleton instance
_reference_store: Optional[SessionReferenceStore] = None


def get_reference_store() -> SessionReferenceStore:
    """Get the global reference store instance."""
    global _reference_store
    if _reference_store is None:
        _reference_store = SessionReferenceStore()
    return _reference_store
