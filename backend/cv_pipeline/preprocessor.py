"""
Image Preprocessor for CV Pipeline

Handles image decoding, validation, resizing, and format conversion
for use with YOLO and OCR models.
"""

import base64
import io
from typing import Tuple, Optional
from dataclasses import dataclass

import numpy as np
from PIL import Image
import cv2

from .data_classes import BoundingBox


@dataclass
class PreprocessedImage:
    """Result of image preprocessing."""
    image: np.ndarray  # BGR format for OpenCV/YOLO
    original_size: Tuple[int, int]  # (width, height)
    processed_size: Tuple[int, int]  # (width, height)
    scale_factor: Tuple[float, float]  # (scale_x, scale_y)


class ImagePreprocessor:
    """
    Preprocesses images for CV pipeline processing.

    Handles base64 decoding, format validation, resizing,
    and conversion to BGR numpy arrays.
    """

    def __init__(
        self,
        max_size_mb: int = 10,
        supported_formats: list = None,
        default_resize_width: int = 1920,
        default_resize_height: int = 1080
    ):
        """
        Initialize the preprocessor.

        Args:
            max_size_mb: Maximum allowed image size in megabytes
            supported_formats: List of supported image formats
            default_resize_width: Default width to resize large images
            default_resize_height: Default height to resize large images
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.supported_formats = supported_formats or ["png", "jpg", "jpeg", "bmp", "webp"]
        self.default_resize_width = default_resize_width
        self.default_resize_height = default_resize_height

    def decode_base64(self, base64_string: str) -> bytes:
        """
        Decode base64 image string, handling data URI prefix.

        Args:
            base64_string: Base64 encoded image string (with or without data URI)

        Returns:
            Decoded image bytes

        Raises:
            ValueError: If decoding fails
        """
        try:
            # Remove data URI prefix if present (e.g., "data:image/png;base64,")
            if "," in base64_string:
                base64_string = base64_string.split(",", 1)[1]

            # Remove any whitespace
            base64_string = base64_string.strip()

            return base64.b64decode(base64_string)
        except Exception as e:
            raise ValueError(f"Failed to decode base64 image: {str(e)}")

    def validate_image(self, image_bytes: bytes) -> Tuple[bool, str]:
        """
        Validate image bytes for size and format.

        Args:
            image_bytes: Raw image bytes

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check size
        if len(image_bytes) > self.max_size_bytes:
            size_mb = len(image_bytes) / (1024 * 1024)
            return False, f"Image size ({size_mb:.1f}MB) exceeds maximum ({self.max_size_bytes / (1024 * 1024):.0f}MB)"

        # Try to open and check format
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img_format = img.format.lower() if img.format else "unknown"

            if img_format not in self.supported_formats:
                return False, f"Unsupported format '{img_format}'. Supported: {self.supported_formats}"

            return True, ""
        except Exception as e:
            return False, f"Invalid image: {str(e)}"

    def resize_image(
        self,
        image: np.ndarray,
        max_width: Optional[int] = None,
        max_height: Optional[int] = None,
        maintain_aspect_ratio: bool = True
    ) -> Tuple[np.ndarray, Tuple[float, float]]:
        """
        Resize image while optionally maintaining aspect ratio.

        Args:
            image: BGR numpy array
            max_width: Maximum width (uses default if None)
            max_height: Maximum height (uses default if None)
            maintain_aspect_ratio: Whether to maintain aspect ratio

        Returns:
            Tuple of (resized_image, (scale_x, scale_y))
        """
        max_width = max_width or self.default_resize_width
        max_height = max_height or self.default_resize_height

        height, width = image.shape[:2]

        # Check if resizing is needed
        if width <= max_width and height <= max_height:
            return image, (1.0, 1.0)

        if maintain_aspect_ratio:
            # Calculate scale to fit within bounds
            scale = min(max_width / width, max_height / height)
            new_width = int(width * scale)
            new_height = int(height * scale)
            scale_x = scale_y = scale
        else:
            new_width = min(width, max_width)
            new_height = min(height, max_height)
            scale_x = new_width / width
            scale_y = new_height / height

        resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        return resized, (scale_x, scale_y)

    def to_numpy_bgr(self, image_bytes: bytes) -> np.ndarray:
        """
        Convert image bytes to BGR numpy array.

        Args:
            image_bytes: Raw image bytes

        Returns:
            BGR numpy array suitable for OpenCV/YOLO
        """
        # Open with PIL
        pil_image = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB if necessary
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        # Convert to numpy and then BGR
        rgb_array = np.array(pil_image)
        bgr_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)

        return bgr_array

    def preprocess(
        self,
        base64_string: str,
        resize: bool = True,
        max_width: Optional[int] = None,
        max_height: Optional[int] = None
    ) -> PreprocessedImage:
        """
        Full preprocessing pipeline for an image.

        Args:
            base64_string: Base64 encoded image string
            resize: Whether to resize large images
            max_width: Maximum width for resizing
            max_height: Maximum height for resizing

        Returns:
            PreprocessedImage with BGR array and size info

        Raises:
            ValueError: If image validation fails
        """
        # Decode base64
        image_bytes = self.decode_base64(base64_string)

        # Validate
        is_valid, error_msg = self.validate_image(image_bytes)
        if not is_valid:
            raise ValueError(error_msg)

        # Convert to numpy BGR
        bgr_image = self.to_numpy_bgr(image_bytes)
        height, width = bgr_image.shape[:2]
        original_size = (width, height)

        # Resize if needed
        if resize:
            processed_image, scale_factor = self.resize_image(
                bgr_image, max_width, max_height
            )
            proc_height, proc_width = processed_image.shape[:2]
            processed_size = (proc_width, proc_height)
        else:
            processed_image = bgr_image
            processed_size = original_size
            scale_factor = (1.0, 1.0)

        return PreprocessedImage(
            image=processed_image,
            original_size=original_size,
            processed_size=processed_size,
            scale_factor=scale_factor
        )

    def scale_bbox_to_original(
        self,
        bbox: BoundingBox,
        scale_factor: Tuple[float, float]
    ) -> BoundingBox:
        """
        Scale bounding box coordinates back to original image size.

        Args:
            bbox: Bounding box in processed image coordinates
            scale_factor: (scale_x, scale_y) used during preprocessing

        Returns:
            BoundingBox in original image coordinates
        """
        scale_x, scale_y = scale_factor

        # Inverse scale to get original coordinates
        return BoundingBox(
            x1=int(bbox.x1 / scale_x),
            y1=int(bbox.y1 / scale_y),
            x2=int(bbox.x2 / scale_x),
            y2=int(bbox.y2 / scale_y)
        )

    def preprocess_from_bytes(
        self,
        image_bytes: bytes,
        resize: bool = True,
        max_width: Optional[int] = None,
        max_height: Optional[int] = None
    ) -> PreprocessedImage:
        """
        Preprocess from raw bytes instead of base64.

        Args:
            image_bytes: Raw image bytes
            resize: Whether to resize large images
            max_width: Maximum width for resizing
            max_height: Maximum height for resizing

        Returns:
            PreprocessedImage with BGR array and size info
        """
        # Validate
        is_valid, error_msg = self.validate_image(image_bytes)
        if not is_valid:
            raise ValueError(error_msg)

        # Convert to numpy BGR
        bgr_image = self.to_numpy_bgr(image_bytes)
        height, width = bgr_image.shape[:2]
        original_size = (width, height)

        # Resize if needed
        if resize:
            processed_image, scale_factor = self.resize_image(
                bgr_image, max_width, max_height
            )
            proc_height, proc_width = processed_image.shape[:2]
            processed_size = (proc_width, proc_height)
        else:
            processed_image = bgr_image
            processed_size = original_size
            scale_factor = (1.0, 1.0)

        return PreprocessedImage(
            image=processed_image,
            original_size=original_size,
            processed_size=processed_size,
            scale_factor=scale_factor
        )
