"""
Google Cloud Vision OCR Engine

Uses Google Cloud Vision API for fast, accurate text extraction.
Requires a Google Cloud API key with Vision API enabled.

Performance: ~2-5 seconds (cloud-based)
Accuracy: ~98.7% on clean documents
"""

import time
import base64
from typing import Dict, List, Optional

import numpy as np
import cv2

from .data_classes import BoundingBox, TextRegion, OCRResult


class GoogleOCREngine:
    """
    Google Cloud Vision OCR engine.

    Uses Google Cloud Vision API for text extraction.
    Requires internet connection and API key.

    Features:
    - Fast cloud-based processing (~2-5 seconds)
    - High accuracy (98.7% on clean documents)
    - Handles multiple languages
    - Free tier: 1,000 units/month
    """

    def __init__(
        self,
        api_key: str,
        language: str = "en",
        confidence_threshold: float = 0.5,
    ):
        """
        Initialize the Google OCR engine.

        Args:
            api_key: Google Cloud API key with Vision API enabled
            language: Language hint for OCR (e.g., 'en', 'es', 'fr')
            confidence_threshold: Minimum confidence for text detection
        """
        self.api_key = api_key
        self.language = language
        self.confidence_threshold = confidence_threshold
        self._client = None

    def _get_client(self):
        """Get or create the Vision API client."""
        if self._client is None:
            try:
                from google.cloud import vision
                # Use API key authentication
                self._client = vision.ImageAnnotatorClient(
                    client_options={"api_key": self.api_key}
                )
                print("[Google-OCR] Vision API client created")
            except ImportError:
                raise ImportError(
                    "google-cloud-vision not installed. "
                    "Run: pip install google-cloud-vision"
                )
        return self._client

    def extract_text(self, image: np.ndarray) -> OCRResult:
        """
        Extract text from an image using Google Cloud Vision API.

        Args:
            image: BGR numpy array (OpenCV format)

        Returns:
            OCRResult with detected text regions
        """
        start_time = time.perf_counter()

        try:
            # Convert BGR to RGB
            if len(image.shape) == 3 and image.shape[2] == 3:
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                rgb_image = image

            # Encode image to PNG bytes
            _, encoded = cv2.imencode('.png', cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR))
            image_bytes = encoded.tobytes()

            # Call Google Cloud Vision API
            text_regions = self._call_vision_api(image_bytes)

            processing_time = (time.perf_counter() - start_time) * 1000
            print(f"[Google-OCR] Extracted {len(text_regions)} text regions in {processing_time:.0f}ms")

            return OCRResult(
                text_regions=text_regions,
                processing_time_ms=processing_time,
                language=self.language
            )

        except Exception as e:
            processing_time = (time.perf_counter() - start_time) * 1000
            print(f"[Google-OCR] Error: {e}")

            return OCRResult(
                text_regions=[],
                processing_time_ms=processing_time,
                language=self.language
            )

    def _call_vision_api(self, image_bytes: bytes) -> List[TextRegion]:
        """
        Call Google Cloud Vision API for text detection.

        Args:
            image_bytes: PNG encoded image bytes

        Returns:
            List of TextRegion objects
        """
        from google.cloud import vision

        client = self._get_client()

        # Create image object
        image = vision.Image(content=image_bytes)

        # Perform text detection
        response = client.text_detection(
            image=image,
            image_context=vision.ImageContext(
                language_hints=[self.language]
            )
        )

        if response.error.message:
            raise Exception(f"Vision API error: {response.error.message}")

        text_regions = []
        annotations = response.text_annotations

        # Skip first annotation (full text), process individual words/lines
        for i, annotation in enumerate(annotations[1:] if len(annotations) > 1 else []):
            vertices = annotation.bounding_poly.vertices

            # Get bounding box coordinates
            x_coords = [v.x for v in vertices]
            y_coords = [v.y for v in vertices]

            bbox = BoundingBox(
                x1=min(x_coords),
                y1=min(y_coords),
                x2=max(x_coords),
                y2=max(y_coords)
            )

            # Google Vision doesn't provide confidence per word in text_detection
            # Use 0.95 as default (high confidence for Google OCR)
            confidence = 0.95

            if confidence >= self.confidence_threshold:
                text_regions.append(TextRegion(
                    text=annotation.description,
                    bbox=bbox,
                    confidence=confidence,
                    language=self.language
                ))

        return text_regions

    def extract_text_from_region(
        self,
        image: np.ndarray,
        bbox: BoundingBox
    ) -> OCRResult:
        """
        Extract text from a specific region of an image.

        Args:
            image: BGR numpy array
            bbox: Bounding box defining the region

        Returns:
            OCRResult for the specified region
        """
        # Crop the region
        cropped = image[bbox.y1:bbox.y2, bbox.x1:bbox.x2]

        if cropped.size == 0:
            return OCRResult(
                text_regions=[],
                processing_time_ms=0,
                language=self.language
            )

        return self.extract_text(cropped)

    def get_engine_info(self) -> Dict:
        """Get information about the OCR engine."""
        return {
            "engine": "google_cloud_vision",
            "language": self.language,
            "confidence_threshold": self.confidence_threshold,
            "requires_internet": True,
            "api_key_configured": bool(self.api_key),
        }

    def is_loaded(self) -> bool:
        """Check if the engine is ready."""
        return bool(self.api_key)


def create_google_ocr_engine_from_settings(settings) -> GoogleOCREngine:
    """
    Factory function to create Google OCR engine from app settings.

    Args:
        settings: Application settings object

    Returns:
        Configured GoogleOCREngine
    """
    api_key = getattr(settings, 'GOOGLE_CLOUD_API_KEY', '')

    if not api_key:
        raise ValueError(
            "GOOGLE_CLOUD_API_KEY not configured. "
            "Set it in .env or config.py"
        )

    return GoogleOCREngine(
        api_key=api_key,
        language=getattr(settings, 'OCR_LANGUAGE', 'en'),
        confidence_threshold=getattr(settings, 'OCR_CONFIDENCE_THRESHOLD', 0.5),
    )
