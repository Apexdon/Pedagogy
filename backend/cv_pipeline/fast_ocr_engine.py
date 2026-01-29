"""
Fast OCR Engine for Target Verification

Optimized for speed over accuracy - suitable for:
- Target application verification (brand keyword matching)
- Fast position updates during scrolling

OCR Engine Priority:
1. Windows OCR (winocr) - Fastest (~50-200ms) on Windows 10+
2. RapidOCR - Fast (~200-400ms), pure Python, good accuracy
3. Tesseract - Legacy fallback (~500-700ms)

For full UI analysis with high accuracy, use PaddleOCR instead.
"""

import platform
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from .data_classes import BoundingBox, TextRegion, OCRResult


# Global cache for lazy loading
_rapidocr_instance = None
_tesseract_initialized = False
_windows_ocr_available: Optional[bool] = None
_rapidocr_available: Optional[bool] = None


def _check_windows_ocr_available() -> bool:
    """Check if Windows OCR (winocr) is available."""
    global _windows_ocr_available

    if _windows_ocr_available is not None:
        return _windows_ocr_available

    # Only available on Windows 10+
    if platform.system() != "Windows":
        _windows_ocr_available = False
        return False

    try:
        # Check Windows version (Windows 10 is version 10.0)
        version = platform.version()
        major_version = int(version.split('.')[0]) if version else 0

        if major_version < 10:
            print("[FastOCR] Windows version < 10, Windows OCR not available")
            _windows_ocr_available = False
            return False

        # Try importing winocr
        import winocr
        _windows_ocr_available = True
        print("[FastOCR] Windows OCR (winocr) is available")
        return True

    except ImportError:
        print("[FastOCR] winocr not installed")
        _windows_ocr_available = False
        return False
    except Exception as e:
        print(f"[FastOCR] Error checking Windows OCR: {e}")
        _windows_ocr_available = False
        return False


def _check_rapidocr_available() -> bool:
    """Check if RapidOCR is available."""
    global _rapidocr_available

    if _rapidocr_available is not None:
        return _rapidocr_available

    try:
        from rapidocr_onnxruntime import RapidOCR
        _rapidocr_available = True
        print("[FastOCR] RapidOCR is available")
        return True
    except ImportError:
        print("[FastOCR] RapidOCR not installed, will try Tesseract")
        _rapidocr_available = False
        return False
    except Exception as e:
        print(f"[FastOCR] Error checking RapidOCR: {e}")
        _rapidocr_available = False
        return False


def _init_tesseract(tesseract_path: Optional[str] = None) -> bool:
    """Initialize Tesseract with the correct path."""
    global _tesseract_initialized

    if _tesseract_initialized:
        return True

    try:
        import pytesseract

        # Set Tesseract path if provided
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path

        # Verify Tesseract is accessible
        version = pytesseract.get_tesseract_version()
        print(f"[FastOCR] Tesseract v{version} initialized")
        _tesseract_initialized = True
        return True

    except Exception as e:
        print(f"[FastOCR] Failed to initialize Tesseract: {e}")
        return False


def _get_rapidocr_instance():
    """Get or create the RapidOCR instance (lazy loaded)."""
    global _rapidocr_instance

    if _rapidocr_instance is None:
        from rapidocr_onnxruntime import RapidOCR
        _rapidocr_instance = RapidOCR()
        print("[FastOCR] RapidOCR instance created")

    return _rapidocr_instance


class FastOCREngine:
    """
    Fast OCR engine optimized for target verification.

    Engine priority:
    1. Windows OCR (~50-200ms) - Windows 10+ only
    2. RapidOCR (~200-400ms) - Cross-platform, pure Python
    3. Tesseract (~500-700ms) - Legacy fallback

    Features:
    - Region-of-interest (ROI) cropping for header-only OCR
    - Automatic engine selection based on availability
    """

    def __init__(
        self,
        language: str = "eng",
        confidence_threshold: float = 0.3,
        tesseract_path: Optional[str] = None,
        prefer_windows_ocr: bool = True,
        header_roi_height: int = 200,  # Default: top 200 pixels for brand text
    ):
        """
        Initialize the Fast OCR engine.

        Args:
            language: Language code for OCR
            confidence_threshold: Minimum confidence for text detection
            tesseract_path: Path to Tesseract executable (auto-detected if None)
            prefer_windows_ocr: If True, use Windows OCR when available
            header_roi_height: Height of header region for ROI-based OCR
        """
        self.language = language
        self.confidence_threshold = confidence_threshold
        self.tesseract_path = tesseract_path
        self.prefer_windows_ocr = prefer_windows_ocr
        self.header_roi_height = header_roi_height
        self._initialized = False
        self._engine_type = "none"  # "windows_ocr", "rapidocr", "tesseract"

    def _ensure_initialized(self) -> None:
        """Ensure the OCR engine is initialized."""
        if self._initialized:
            return

        # Priority 1: Windows OCR (fastest)
        if self.prefer_windows_ocr and _check_windows_ocr_available():
            self._engine_type = "windows_ocr"
            print("[FastOCR] Using Windows OCR (fastest)")
            self._initialized = True
            return

        # Priority 2: RapidOCR (fast, pure Python)
        if _check_rapidocr_available():
            self._engine_type = "rapidocr"
            print("[FastOCR] Using RapidOCR (fast)")
            self._initialized = True
            return

        # Priority 3: Tesseract (legacy fallback)
        if _init_tesseract(self.tesseract_path):
            self._engine_type = "tesseract"
            print("[FastOCR] Using Tesseract (fallback)")
            self._initialized = True
            return

        raise RuntimeError("No OCR engine available. Install rapidocr-onnxruntime or Tesseract.")

    def extract_text(
        self,
        image: np.ndarray,
        use_roi: bool = False,
        roi_height: Optional[int] = None,
    ) -> OCRResult:
        """
        Extract text from an image.

        Args:
            image: BGR or RGB numpy array
            use_roi: If True, only OCR the header region (faster)
            roi_height: Custom ROI height (uses header_roi_height if None)

        Returns:
            OCRResult with detected TextRegions
        """
        self._ensure_initialized()

        start_time = time.perf_counter()

        # Apply ROI cropping if requested
        original_height = image.shape[0]
        roi_offset_y = 0

        if use_roi:
            height = roi_height or self.header_roi_height
            if height < original_height:
                image = image[:height, :]
                roi_offset_y = 0  # ROI starts at top
                print(f"[FastOCR] Using ROI: top {height}px of {original_height}px image")

        # Run OCR based on engine type
        if self._engine_type == "windows_ocr":
            result = self._extract_with_windows_ocr(image)
        elif self._engine_type == "rapidocr":
            result = self._extract_with_rapidocr(image)
        else:
            result = self._extract_with_tesseract(image)

        processing_time = (time.perf_counter() - start_time) * 1000

        # Adjust bounding boxes if ROI was used (coordinates relative to original image)
        # Since we use top ROI, no adjustment needed (roi_offset_y = 0)

        return OCRResult(
            text_regions=result.text_regions,
            processing_time_ms=processing_time,
            language=result.language
        )

    def extract_text_header_only(self, image: np.ndarray) -> OCRResult:
        """
        Extract text from header region only (optimized for brand keyword detection).

        This is ~60-70% faster than full-image OCR.

        Args:
            image: BGR or RGB numpy array

        Returns:
            OCRResult with text from header region
        """
        return self.extract_text(image, use_roi=True)

    def _extract_with_rapidocr(self, image: np.ndarray) -> OCRResult:
        """Extract text using RapidOCR."""
        start_time = time.perf_counter()

        ocr = _get_rapidocr_instance()

        # RapidOCR expects RGB or BGR numpy array
        # Convert BGR to RGB if needed (RapidOCR handles both, but RGB is preferred)
        if len(image.shape) == 3 and image.shape[2] == 3:
            # Assume BGR from OpenCV, convert to RGB
            rgb_image = image[:, :, ::-1]
        else:
            rgb_image = image

        # Run OCR
        result, elapse = ocr(rgb_image)

        processing_time = (time.perf_counter() - start_time) * 1000

        # Process results
        text_regions: List[TextRegion] = []

        if result:
            for item in result:
                # RapidOCR returns: [bbox_points, text, confidence]
                bbox_points, text, confidence = item

                if not text or not text.strip():
                    continue

                if confidence < self.confidence_threshold:
                    continue

                # bbox_points is [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
                # Convert to x1, y1, x2, y2
                xs = [p[0] for p in bbox_points]
                ys = [p[1] for p in bbox_points]

                bbox = BoundingBox(
                    x1=int(min(xs)),
                    y1=int(min(ys)),
                    x2=int(max(xs)),
                    y2=int(max(ys))
                )

                text_region = TextRegion(
                    text=text.strip(),
                    bbox=bbox,
                    confidence=float(confidence),
                    metadata={"engine": "rapidocr"}
                )
                text_regions.append(text_region)

        return OCRResult(
            text_regions=text_regions,
            processing_time_ms=processing_time,
            language=self.language
        )

    def _extract_with_tesseract(self, image: np.ndarray) -> OCRResult:
        """Extract text using Tesseract."""
        import pytesseract

        start_time = time.perf_counter()

        # Convert numpy array to PIL Image
        if len(image.shape) == 3 and image.shape[2] == 3:
            # Assume BGR, convert to RGB
            pil_image = Image.fromarray(image[:, :, ::-1])
        else:
            pil_image = Image.fromarray(image)

        # Get detailed OCR data with bounding boxes
        ocr_data = pytesseract.image_to_data(
            pil_image,
            lang=self.language,
            output_type=pytesseract.Output.DICT
        )

        processing_time = (time.perf_counter() - start_time) * 1000

        # Process results
        text_regions: List[TextRegion] = []
        n_boxes = len(ocr_data['text'])

        for i in range(n_boxes):
            text = ocr_data['text'][i].strip()
            conf = float(ocr_data['conf'][i])

            # Skip empty text or low confidence
            if not text or conf < 0:
                continue

            # Convert confidence from 0-100 to 0-1
            confidence = conf / 100.0

            if confidence < self.confidence_threshold:
                continue

            # Get bounding box
            x = int(ocr_data['left'][i])
            y = int(ocr_data['top'][i])
            w = int(ocr_data['width'][i])
            h = int(ocr_data['height'][i])

            bbox = BoundingBox(
                x1=x,
                y1=y,
                x2=x + w,
                y2=y + h
            )

            text_region = TextRegion(
                text=text,
                bbox=bbox,
                confidence=confidence,
                metadata={"engine": "tesseract"}
            )
            text_regions.append(text_region)

        return OCRResult(
            text_regions=text_regions,
            processing_time_ms=processing_time,
            language=self.language
        )

    def _extract_with_windows_ocr(self, image: np.ndarray) -> OCRResult:
        """Extract text using Windows OCR API."""
        import asyncio
        import concurrent.futures
        import winocr

        start_time = time.perf_counter()

        # Convert numpy array to PIL Image
        if len(image.shape) == 3 and image.shape[2] == 3:
            # Assume BGR, convert to RGB
            pil_image = Image.fromarray(image[:, :, ::-1])
        else:
            pil_image = Image.fromarray(image)

        # Windows OCR is async - run in a separate thread to avoid event loop conflicts
        def run_ocr_sync():
            """Run async OCR in a new event loop within this thread."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(winocr.recognize_pil(pil_image, lang="en"))
            finally:
                loop.close()

        # Run in thread pool to avoid blocking and event loop conflicts
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_ocr_sync)
            result = future.result(timeout=10)  # 10 second timeout

        processing_time = (time.perf_counter() - start_time) * 1000

        # Process results
        text_regions: List[TextRegion] = []

        if result and hasattr(result, 'lines'):
            for line in result.lines:
                text = line.text.strip() if hasattr(line, 'text') else ""

                if not text:
                    continue

                # Get bounding box from words
                if hasattr(line, 'words') and line.words:
                    # Combine all word bboxes - winocr uses bounding_rect property
                    x1 = min(w.bounding_rect.x for w in line.words)
                    y1 = min(w.bounding_rect.y for w in line.words)
                    x2 = max(w.bounding_rect.x + w.bounding_rect.width for w in line.words)
                    y2 = max(w.bounding_rect.y + w.bounding_rect.height for w in line.words)
                else:
                    # Fallback to line bbox if available
                    x1, y1, x2, y2 = 0, 0, 100, 20  # Default

                bbox = BoundingBox(
                    x1=int(x1),
                    y1=int(y1),
                    x2=int(x2),
                    y2=int(y2)
                )

                text_region = TextRegion(
                    text=text,
                    bbox=bbox,
                    confidence=0.9,  # Windows OCR doesn't provide confidence
                    metadata={"engine": "windows_ocr"}
                )
                text_regions.append(text_region)

        return OCRResult(
            text_regions=text_regions,
            processing_time_ms=processing_time,
            language="en"
        )

    def get_engine_info(self) -> Dict:
        """Get information about the OCR engine."""
        self._ensure_initialized()
        return {
            "engine": "fast_ocr",
            "backend": self._engine_type,
            "language": self.language,
            "confidence_threshold": self.confidence_threshold,
            "header_roi_height": self.header_roi_height,
            "initialized": self._initialized
        }

    def is_loaded(self) -> bool:
        """Check if engine is initialized."""
        return self._initialized


# Global fast OCR instance (lazy loaded)
_fast_ocr_instance: Optional[FastOCREngine] = None


def get_fast_ocr_engine(settings=None) -> FastOCREngine:
    """
    Get or create the global fast OCR engine instance.

    Args:
        settings: Optional app settings for configuration

    Returns:
        FastOCREngine instance
    """
    global _fast_ocr_instance

    if _fast_ocr_instance is None:
        tesseract_path = None
        header_roi_height = 200

        if settings:
            if hasattr(settings, 'TESSERACT_PATH'):
                tesseract_path = settings.TESSERACT_PATH
            if hasattr(settings, 'FAST_OCR_HEADER_ROI_HEIGHT'):
                header_roi_height = settings.FAST_OCR_HEADER_ROI_HEIGHT

        _fast_ocr_instance = FastOCREngine(
            language="eng",
            confidence_threshold=0.3,
            tesseract_path=tesseract_path,
            prefer_windows_ocr=True,
            header_roi_height=header_roi_height,
        )

    return _fast_ocr_instance


def create_fast_ocr_engine_from_settings(settings) -> FastOCREngine:
    """
    Factory function to create Fast OCR engine from app settings.

    Args:
        settings: Application settings object

    Returns:
        Configured FastOCREngine
    """
    return FastOCREngine(
        language=getattr(settings, 'FAST_OCR_LANGUAGE', 'eng'),
        confidence_threshold=getattr(settings, 'FAST_OCR_CONFIDENCE_THRESHOLD', 0.3),
        tesseract_path=getattr(settings, 'TESSERACT_PATH', None),
        prefer_windows_ocr=getattr(settings, 'FAST_OCR_PREFER_WINDOWS', True),
        header_roi_height=getattr(settings, 'FAST_OCR_HEADER_ROI_HEIGHT', 200),
    )
