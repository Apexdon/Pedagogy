"""
Context Engine - Fusion Layer for CV Pipeline

Combines UI detection (OmniParser or YOLO) and OCR text extraction
(PaddleOCR or EasyOCR) into a unified screen state representation.

Supports parallel processing for improved performance.
"""

import concurrent.futures
import re
import time
import uuid
from datetime import datetime
from typing import List, Optional, Tuple, Union

import numpy as np
import cv2

from .data_classes import (
    BoundingBox,
    UIElement,
    TextRegion,
    DetectionResult,
    OCRResult,
    ScreenState
)
from .preprocessor import ImagePreprocessor, PreprocessedImage
from .yolo_detector import YOLODetector
from .ocr_engine import OCREngine


class ContextEngine:
    """
    Unified CV analysis engine that combines UI detection and OCR.

    Coordinates the preprocessing, detection, OCR, and fusion
    of results into a complete screen state representation.

    Supports both OmniParser (recommended) and YOLO (legacy) detectors.
    """

    def __init__(
        self,
        preprocessor: ImagePreprocessor,
        detector,  # Can be OmniParserDetector or YOLODetector
        ocr_engine: OCREngine
    ):
        """
        Initialize the context engine.

        Args:
            preprocessor: Image preprocessor instance
            detector: UI detector instance (OmniParserDetector or YOLODetector)
            ocr_engine: OCR engine instance
        """
        self.preprocessor = preprocessor
        self.detector = detector
        self.ocr_engine = ocr_engine

        # Load cropping and filter settings - use get_settings() for fresh values
        from app.config import get_settings
        fresh_settings = get_settings()
        self.crop_browser_chrome = getattr(fresh_settings, 'CV_CROP_BROWSER_CHROME', True)
        self.browser_chrome_height = getattr(fresh_settings, 'CV_BROWSER_CHROME_HEIGHT', 120)
        self.filter_single_char = getattr(fresh_settings, 'CV_FILTER_SINGLE_CHAR_LABELS', True)
        self.filter_garbage = getattr(fresh_settings, 'CV_FILTER_OCR_GARBAGE', True)
        self.min_label_length = getattr(fresh_settings, 'CV_MIN_LABEL_LENGTH', 2)
        print(f"[ContextEngine] Settings loaded: crop={self.crop_browser_chrome}, crop_height={self.browser_chrome_height}, filter_single_char={self.filter_single_char}, filter_garbage={self.filter_garbage}, min_label_length={self.min_label_length}")

    def _crop_browser_chrome(self, image: np.ndarray) -> Tuple[np.ndarray, int]:
        """
        Crop browser chrome (tabs, toolbar, bookmarks) from top of image.

        Args:
            image: BGR numpy array

        Returns:
            Tuple of (cropped_image, crop_offset_y)
        """
        # Crop only browser chrome (tabs + URL bar), keep website header visible
        # At 640x360 resolution: browser chrome ~25-35px, website nav starts ~40px
        crop_enabled = True
        crop_height = 40  # Only remove browser tabs/URL bar, not website content
        print(f"[ContextEngine] _crop_browser_chrome: HARDCODED crop_enabled={crop_enabled}, crop_height={crop_height}")

        if not crop_enabled:
            print("[ContextEngine] Cropping DISABLED - skipping")
            return image, 0

        height = image.shape[0]
        crop_y = min(crop_height, height // 4)  # Don't crop more than 25% of image

        if crop_y > 0:
            cropped = image[crop_y:, :, :]
            print(f"[ContextEngine] Cropped {crop_y}px browser chrome from top")
            return cropped, crop_y

        return image, 0

    def _analyze_parallel(
        self,
        image: np.ndarray,
        timing_breakdown: dict,
        use_sequential: bool = False  # Set True to test sequential execution
    ) -> Tuple[DetectionResult, OCRResult, dict]:
        """
        Run YOLO and OCR on full image (parallel or sequential for profiling).

        Args:
            image: Cropped BGR image
            timing_breakdown: Dict to accumulate timing info
            use_sequential: If True, run sequentially instead of parallel (for profiling)

        Returns:
            Tuple of (detection_result, ocr_result, updated_timing_breakdown)
        """
        if use_sequential:
            return self._analyze_sequential(image, timing_breakdown)

        # Parallel execution with detailed timing
        wall_start = time.perf_counter()

        # Track precise start/end times for each task
        task_timings = {}

        def run_detection():
            start = time.perf_counter()
            result = self.detector.detect(image)
            end = time.perf_counter()
            task_timings['det_start'] = (start - wall_start) * 1000
            task_timings['det_end'] = (end - wall_start) * 1000
            return result

        def run_ocr():
            start = time.perf_counter()
            result = self.ocr_engine.extract_text(image)
            end = time.perf_counter()
            task_timings['ocr_start'] = (start - wall_start) * 1000
            task_timings['ocr_end'] = (end - wall_start) * 1000
            return result

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            detection_future = executor.submit(run_detection)
            ocr_future = executor.submit(run_ocr)

            detection_result = detection_future.result()
            ocr_result = ocr_future.result()

        parallel_time = (time.perf_counter() - wall_start) * 1000

        # Calculate overlap time (when both tasks were running)
        det_start = task_timings.get('det_start', 0)
        det_end = task_timings.get('det_end', 0)
        ocr_start = task_timings.get('ocr_start', 0)
        ocr_end = task_timings.get('ocr_end', 0)

        overlap_start = max(det_start, ocr_start)
        overlap_end = min(det_end, ocr_end)
        overlap_time = max(0, overlap_end - overlap_start)

        # Calculate contention penalty (how much slower vs sequential theoretical)
        det_duration = det_end - det_start
        ocr_duration = ocr_end - ocr_start
        sequential_theoretical = det_duration + ocr_duration
        contention_overhead = parallel_time - max(det_duration, ocr_duration)

        timing_breakdown['detection'] = detection_result.processing_time_ms
        timing_breakdown['ocr'] = ocr_result.processing_time_ms
        timing_breakdown['parallel_total'] = parallel_time
        timing_breakdown['overlap_time'] = overlap_time
        timing_breakdown['contention_overhead'] = contention_overhead

        print(f"[ContextEngine] Parallel processing took {parallel_time:.0f}ms")
        print(f"[ContextEngine] PARALLEL PROFILING:")
        print(f"  Detection: started={det_start:.0f}ms, ended={det_end:.0f}ms, duration={det_duration:.0f}ms")
        print(f"  OCR:       started={ocr_start:.0f}ms, ended={ocr_end:.0f}ms, duration={ocr_duration:.0f}ms")
        print(f"  Overlap (both running): {overlap_time:.0f}ms")
        print(f"  Contention overhead: {contention_overhead:.0f}ms")
        print(f"  Sequential theoretical: {sequential_theoretical:.0f}ms (if no contention)")

        return detection_result, ocr_result, timing_breakdown

    def _analyze_sequential(
        self,
        image: np.ndarray,
        timing_breakdown: dict
    ) -> Tuple[DetectionResult, OCRResult, dict]:
        """
        Sequential execution for profiling comparison (no CPU contention).

        Args:
            image: Cropped BGR image
            timing_breakdown: Dict to accumulate timing info

        Returns:
            Tuple of (detection_result, ocr_result, updated_timing_breakdown)
        """
        sequential_start = time.perf_counter()

        # Run detection first
        det_start = time.perf_counter()
        detection_result = self.detector.detect(image)
        det_time = (time.perf_counter() - det_start) * 1000

        # Then run OCR
        ocr_start = time.perf_counter()
        ocr_result = self.ocr_engine.extract_text(image)
        ocr_time = (time.perf_counter() - ocr_start) * 1000

        sequential_time = (time.perf_counter() - sequential_start) * 1000

        timing_breakdown['detection'] = det_time
        timing_breakdown['ocr'] = ocr_time
        timing_breakdown['parallel_total'] = sequential_time  # Keep same key for compatibility
        timing_breakdown['sequential_mode'] = True

        print(f"[ContextEngine] SEQUENTIAL processing took {sequential_time:.0f}ms")
        print(f"[ContextEngine] SEQUENTIAL PROFILING:")
        print(f"  Detection: {det_time:.0f}ms")
        print(f"  OCR: {ocr_time:.0f}ms")
        print(f"  Total: {sequential_time:.0f}ms (no contention)")

        return detection_result, ocr_result, timing_breakdown

    def _analyze_multiprocess(
        self,
        image: np.ndarray,
        timing_breakdown: dict
    ) -> Tuple[DetectionResult, OCRResult, dict]:
        """
        Multiprocessing execution - runs YOLO and OCR in separate processes.

        This eliminates CPU contention by giving each task its own memory space.
        Each process can use full CPU resources without cache thrashing.

        Args:
            image: Cropped BGR image
            timing_breakdown: Dict to accumulate timing info

        Returns:
            Tuple of (detection_result, ocr_result, updated_timing_breakdown)
        """
        from .multiprocess_executor import get_multiprocess_executor

        wall_start = time.perf_counter()

        # Get or create the global executor
        executor = get_multiprocess_executor()

        # Start workers if not already running
        if not executor.is_running():
            print("[ContextEngine] Starting multiprocess workers...")
            if not executor.start(timeout=120.0):
                print("[ContextEngine] Multiprocess workers failed to start, falling back to threading")
                return self._analyze_parallel(image, timing_breakdown, use_sequential=False)

        # Run parallel analysis using separate processes
        detection_data, ocr_result_data, mp_timing = executor.run_parallel(image)

        wall_time = (time.perf_counter() - wall_start) * 1000

        # detection_data is a DetectionResult object from the worker
        # If it's already a DetectionResult, use it directly; otherwise wrap the list
        if isinstance(detection_data, DetectionResult):
            detection_result = detection_data
        else:
            # Fallback: wrap elements list in DetectionResult
            detection_result = DetectionResult(
                elements=detection_data or [],
                processing_time_ms=mp_timing['yolo_ms'],
                model_name="omniparser",
                image_size=(image.shape[1], image.shape[0])
            )

        # OCR result is already in correct format from worker
        if isinstance(ocr_result_data, OCRResult):
            ocr_result = ocr_result_data
        else:
            ocr_result = OCRResult(
                text_regions=[],
                processing_time_ms=mp_timing['ocr_ms'],
                language="en"
            )

        timing_breakdown['detection'] = mp_timing['yolo_ms']
        timing_breakdown['ocr'] = mp_timing['ocr_ms']
        timing_breakdown['parallel_total'] = wall_time
        timing_breakdown['ipc_write_ms'] = mp_timing['ipc_write_ms']
        timing_breakdown['ipc_read_ms'] = mp_timing['ipc_read_ms']
        timing_breakdown['multiprocess_mode'] = True

        print(f"[ContextEngine] MULTIPROCESS processing took {wall_time:.0f}ms")
        print(f"[ContextEngine] MULTIPROCESS PROFILING:")
        print(f"  Detection: {mp_timing['yolo_ms']:.0f}ms (in worker process)")
        print(f"  OCR:       {mp_timing['ocr_ms']:.0f}ms (in worker process)")
        print(f"  IPC Write: {mp_timing['ipc_write_ms']:.0f}ms")
        print(f"  IPC Read:  {mp_timing['ipc_read_ms']:.0f}ms")
        print(f"  Wall Time: {wall_time:.0f}ms")

        return detection_result, ocr_result, timing_breakdown

    def _analyze_targeted(
        self,
        image: np.ndarray,
        timing_breakdown: dict
    ) -> Tuple[DetectionResult, OCRResult, dict]:
        """
        Targeted OCR approach: Run YOLO first, then OCR only on detected UI regions.

        This dramatically reduces OCR workload by only processing regions where
        UI elements were detected, instead of the full image.

        Args:
            image: Cropped BGR image
            timing_breakdown: Dict to accumulate timing info

        Returns:
            Tuple of (detection_result, ocr_result, updated_timing_breakdown)
        """
        # Step 1: Run YOLO detection first
        detection_start = time.perf_counter()
        detection_result = self.detector.detect(image)
        detection_time = (time.perf_counter() - detection_start) * 1000
        timing_breakdown['detection'] = detection_time
        print(f"[ContextEngine] YOLO detection: {len(detection_result.elements)} elements in {detection_time:.0f}ms")

        # Step 2: OCR only on detected UI element regions
        ocr_start = time.perf_counter()
        all_text_regions: List[TextRegion] = []

        if detection_result.elements:
            # Expand bounding boxes slightly to capture nearby text (labels often outside element)
            padding = 10  # pixels

            for elem in detection_result.elements:
                # Get padded region (clamp to image bounds)
                height, width = image.shape[:2]
                x1 = max(0, elem.bbox.x1 - padding)
                y1 = max(0, elem.bbox.y1 - padding)
                x2 = min(width, elem.bbox.x2 + padding)
                y2 = min(height, elem.bbox.y2 + padding)

                # Skip very small regions
                if (x2 - x1) < 20 or (y2 - y1) < 10:
                    continue

                # Crop region
                region_image = image[y1:y2, x1:x2]

                # Run OCR on this region
                region_result = self.ocr_engine.extract_text(region_image)

                # Adjust coordinates back to full image space
                for text_region in region_result.text_regions:
                    adjusted_bbox = BoundingBox(
                        x1=text_region.bbox.x1 + x1,
                        y1=text_region.bbox.y1 + y1,
                        x2=text_region.bbox.x2 + x1,
                        y2=text_region.bbox.y2 + y1
                    )
                    adjusted_region = TextRegion(
                        text=text_region.text,
                        bbox=adjusted_bbox,
                        confidence=text_region.confidence,
                        metadata={**text_region.metadata, "source_element": elem.element_id}
                    )
                    all_text_regions.append(adjusted_region)

        ocr_time = (time.perf_counter() - ocr_start) * 1000
        timing_breakdown['ocr'] = ocr_time
        timing_breakdown['targeted_regions'] = len(detection_result.elements)
        print(f"[ContextEngine] Targeted OCR: {len(all_text_regions)} text regions from {len(detection_result.elements)} UI elements in {ocr_time:.0f}ms")

        # Create OCR result
        ocr_result = OCRResult(
            text_regions=all_text_regions,
            processing_time_ms=ocr_time,
            language=getattr(self.ocr_engine, 'language', 'en')
        )

        return detection_result, ocr_result, timing_breakdown

    def _filter_labels(self, elements: List[UIElement]) -> List[UIElement]:
        """
        Post-process elements to filter out low-quality labels.

        Filters:
        - Single-character labels (usually icon misdetections)
        - OCR garbage (non-alphanumeric characters)
        - Labels below minimum length

        Args:
            elements: List of UI elements with labels

        Returns:
            Filtered list of elements
        """
        print(f"[ContextEngine] _filter_labels called: filter_single_char={self.filter_single_char}, filter_garbage={self.filter_garbage}, min_label_length={self.min_label_length}")

        if not self.filter_single_char and not self.filter_garbage:
            print("[ContextEngine] Filtering disabled, returning elements unchanged")
            return elements

        filtered = []
        removed_count = 0

        for elem in elements:
            label = elem.label

            # If no label, keep element as-is
            if not label:
                filtered.append(elem)
                continue

            # Filter single-character labels
            if self.filter_single_char and len(label.strip()) < self.min_label_length:
                # Clear the label but keep the element
                filtered.append(UIElement(
                    element_id=elem.element_id,
                    element_type=elem.element_type,
                    bbox=elem.bbox,
                    confidence=elem.confidence,
                    label=None,  # Remove bad label
                    metadata=elem.metadata
                ))
                removed_count += 1
                continue

            # Filter OCR garbage (labels with mostly non-alphanumeric characters)
            if self.filter_garbage:
                # Count alphanumeric characters
                alnum_count = sum(1 for c in label if c.isalnum())
                total_count = len(label.replace(' ', ''))

                # If less than 50% alphanumeric, it's likely garbage
                if total_count > 0 and alnum_count / total_count < 0.5:
                    filtered.append(UIElement(
                        element_id=elem.element_id,
                        element_type=elem.element_type,
                        bbox=elem.bbox,
                        confidence=elem.confidence,
                        label=None,  # Remove garbage label
                        metadata=elem.metadata
                    ))
                    removed_count += 1
                    continue

            # Label passed all filters
            filtered.append(elem)

        if removed_count > 0:
            print(f"[ContextEngine] Filtered {removed_count} low-quality labels")

        return filtered

    def _adjust_coordinates_for_crop(
        self,
        elements: List[UIElement],
        text_regions: List[TextRegion],
        crop_offset_y: int
    ) -> Tuple[List[UIElement], List[TextRegion]]:
        """
        Adjust bbox coordinates to account for browser chrome cropping.
        Adds the crop offset back to all Y coordinates.

        Args:
            elements: List of UI elements
            text_regions: List of text regions
            crop_offset_y: Pixels cropped from top

        Returns:
            Tuple of (adjusted_elements, adjusted_text_regions)
        """
        if crop_offset_y == 0:
            return elements, text_regions

        adjusted_elements = []
        for elem in elements:
            adjusted_bbox = BoundingBox(
                x1=elem.bbox.x1,
                y1=elem.bbox.y1 + crop_offset_y,
                x2=elem.bbox.x2,
                y2=elem.bbox.y2 + crop_offset_y
            )
            adjusted_elements.append(UIElement(
                element_id=elem.element_id,
                element_type=elem.element_type,
                bbox=adjusted_bbox,
                confidence=elem.confidence,
                label=elem.label,
                metadata=elem.metadata
            ))

        adjusted_text_regions = []
        for region in text_regions:
            adjusted_bbox = BoundingBox(
                x1=region.bbox.x1,
                y1=region.bbox.y1 + crop_offset_y,
                x2=region.bbox.x2,
                y2=region.bbox.y2 + crop_offset_y
            )
            adjusted_text_regions.append(TextRegion(
                text=region.text,
                bbox=adjusted_bbox,
                confidence=region.confidence,
                metadata=region.metadata
            ))

        return adjusted_elements, adjusted_text_regions

    def analyze(
        self,
        base64_image: str,
        resize: bool = True,
        fuse_labels: bool = True,
        targeted_ocr: bool = False  # Parallel approach needed - targeted misses text outside UI elements
    ) -> ScreenState:
        """
        Full analysis pipeline: preprocess -> detect -> OCR -> fuse.

        Args:
            base64_image: Base64 encoded image string
            resize: Whether to resize large images
            fuse_labels: Whether to associate text with UI elements
            targeted_ocr: If True, only OCR detected UI element regions (faster).
                          If False, OCR full image in parallel with detection (original behavior).

        Returns:
            Complete ScreenState with elements and text
        """
        start_time = time.perf_counter()
        timing_breakdown = {}

        # Preprocess image
        preprocess_start = time.perf_counter()
        preprocessed = self.preprocessor.preprocess(base64_image, resize=resize)
        preprocess_time = (time.perf_counter() - preprocess_start) * 1000
        timing_breakdown['preprocess'] = preprocess_time
        print(f"[ContextEngine] Preprocess took {preprocess_time:.0f}ms")

        # Crop browser chrome (tabs, toolbar, bookmarks) to reduce noise
        crop_start = time.perf_counter()
        cropped_image, crop_offset_y = self._crop_browser_chrome(preprocessed.image)
        crop_time = (time.perf_counter() - crop_start) * 1000
        timing_breakdown['crop'] = crop_time

        if targeted_ocr:
            # NEW: Sequential approach - YOLO first, then OCR only on detected regions
            # This dramatically reduces OCR workload (30 regions vs 140)
            detection_result, ocr_result, timing_breakdown = self._analyze_targeted(
                cropped_image, timing_breakdown
            )
        else:
            # ORIGINAL: Run detection and OCR on the full cropped image
            # Check execution mode from settings
            from app.config import get_settings
            cv_settings = get_settings()
            use_sequential = getattr(cv_settings, 'CV_SEQUENTIAL_MODE', False)
            parallel_mode = getattr(cv_settings, 'CV_PARALLEL_MODE', 'threading')

            if parallel_mode == 'multiprocessing':
                # Use separate processes for YOLO and OCR (eliminates CPU contention)
                detection_result, ocr_result, timing_breakdown = self._analyze_multiprocess(
                    cropped_image, timing_breakdown
                )
            elif use_sequential:
                # Sequential mode for profiling
                detection_result, ocr_result, timing_breakdown = self._analyze_sequential(
                    cropped_image, timing_breakdown
                )
            else:
                # Default threading mode
                detection_result, ocr_result, timing_breakdown = self._analyze_parallel(
                    cropped_image, timing_breakdown, use_sequential=False
                )

        print(f"[ContextEngine] Detection found {len(detection_result.elements)} elements in {detection_result.processing_time_ms:.0f}ms")
        print(f"[ContextEngine] OCR found {len(ocr_result.text_regions)} text regions in {ocr_result.processing_time_ms:.0f}ms")

        # Log sample OCR text
        if ocr_result.text_regions:
            sample_texts = [r.text for r in ocr_result.text_regions[:10]]
            print(f"[ContextEngine] Sample OCR texts: {sample_texts}")

        # Scale coordinates back to original image size
        scale_start = time.perf_counter()
        elements = self._scale_elements_to_original(
            detection_result.elements,
            preprocessed.scale_factor
        )
        text_regions = self._scale_text_regions_to_original(
            ocr_result.text_regions,
            preprocessed.scale_factor
        )
        scale_time = (time.perf_counter() - scale_start) * 1000
        timing_breakdown['scaling'] = scale_time

        # Fuse text labels with UI elements
        fusion_start = time.perf_counter()
        if fuse_labels:
            elements = self._fuse_labels_with_elements(elements, text_regions)

            # Count elements with labels after fusion
            labeled_count = sum(1 for e in elements if e.label)
            print(f"[ContextEngine] After fusion: {labeled_count}/{len(elements)} elements have labels")
        fusion_time = (time.perf_counter() - fusion_start) * 1000
        timing_breakdown['fusion'] = fusion_time

        # Adjust coordinates for browser chrome cropping
        # Note: crop_offset_y is in processed (resized) space, scale it back to original
        if crop_offset_y > 0:
            scaled_crop_offset = int(crop_offset_y / preprocessed.scale_factor[1])
            elements, text_regions = self._adjust_coordinates_for_crop(
                elements, text_regions, scaled_crop_offset
            )
            print(f"[ContextEngine] Adjusted coordinates: crop_offset={crop_offset_y}px (processed) -> {scaled_crop_offset}px (original)")

        # Post-process: filter out single-character and garbage labels
        filter_start = time.perf_counter()
        elements = self._filter_labels(elements)
        filter_time = (time.perf_counter() - filter_start) * 1000
        timing_breakdown['filter'] = filter_time

        total_time = (time.perf_counter() - start_time) * 1000
        timing_breakdown['total'] = total_time

        # Print detailed timing summary
        self._print_timing_summary(timing_breakdown, detection_result, ocr_result)

        return ScreenState(
            capture_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            image_size=preprocessed.original_size,
            elements=elements,
            text_regions=text_regions,
            processing_time_ms=total_time,
            metadata={
                "detection_time_ms": detection_result.processing_time_ms,
                "detection_timing": detection_result.timing.to_dict() if detection_result.timing else None,  # Per-phase detection timing
                "ocr_time_ms": ocr_result.processing_time_ms,
                "ocr_detection_time_ms": getattr(ocr_result, 'detection_time_ms', 0),  # Text detection phase
                "ocr_recognition_time_ms": getattr(ocr_result, 'recognition_time_ms', 0),  # Text recognition phase
                "ocr_region_timings": [rt.to_dict() for rt in ocr_result.region_timings] if ocr_result.region_timings else None,  # Per-region timing
                "model_name": detection_result.model_name,
                "ocr_language": ocr_result.language,
                "resized": resize,
                "original_size": preprocessed.original_size,
                "processed_size": preprocessed.processed_size
            }
        )

    def analyze_from_bytes(
        self,
        image_bytes: bytes,
        resize: bool = True,
        fuse_labels: bool = True
    ) -> ScreenState:
        """
        Analyze from raw image bytes.

        Args:
            image_bytes: Raw image bytes
            resize: Whether to resize large images
            fuse_labels: Whether to associate text with UI elements

        Returns:
            Complete ScreenState
        """
        start_time = time.perf_counter()

        # Preprocess image
        preprocessed = self.preprocessor.preprocess_from_bytes(image_bytes, resize=resize)

        # Run detection and OCR in parallel for better performance
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            detection_future = executor.submit(self.detector.detect, preprocessed.image)
            ocr_future = executor.submit(self.ocr_engine.extract_text, preprocessed.image)

            detection_result = detection_future.result()
            ocr_result = ocr_future.result()

        # Scale coordinates back to original image size
        elements = self._scale_elements_to_original(
            detection_result.elements,
            preprocessed.scale_factor
        )
        text_regions = self._scale_text_regions_to_original(
            ocr_result.text_regions,
            preprocessed.scale_factor
        )

        # Fuse text labels with UI elements
        if fuse_labels:
            elements = self._fuse_labels_with_elements(elements, text_regions)

        total_time = (time.perf_counter() - start_time) * 1000

        return ScreenState(
            capture_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            image_size=preprocessed.original_size,
            elements=elements,
            text_regions=text_regions,
            processing_time_ms=total_time,
            metadata={
                "detection_time_ms": detection_result.processing_time_ms,
                "ocr_time_ms": ocr_result.processing_time_ms,
                "ocr_detection_time_ms": getattr(ocr_result, 'detection_time_ms', 0),  # Text detection phase
                "ocr_recognition_time_ms": getattr(ocr_result, 'recognition_time_ms', 0),  # Text recognition phase
                "model_name": detection_result.model_name,
                "ocr_language": ocr_result.language
            }
        )

    def detect_ui_only(
        self,
        base64_image: str,
        resize: bool = True
    ) -> DetectionResult:
        """
        Run only UI element detection (no OCR).

        Args:
            base64_image: Base64 encoded image string
            resize: Whether to resize large images

        Returns:
            DetectionResult with UI elements
        """
        preprocessed = self.preprocessor.preprocess(base64_image, resize=resize)
        result = self.detector.detect(preprocessed.image)

        # Scale coordinates back to original
        scaled_elements = self._scale_elements_to_original(
            result.elements,
            preprocessed.scale_factor
        )

        return DetectionResult(
            elements=scaled_elements,
            processing_time_ms=result.processing_time_ms,
            model_name=result.model_name,
            image_size=preprocessed.original_size
        )

    def extract_text_only(
        self,
        base64_image: str,
        resize: bool = True
    ) -> OCRResult:
        """
        Run only OCR text extraction (no UI detection).

        Args:
            base64_image: Base64 encoded image string
            resize: Whether to resize large images

        Returns:
            OCRResult with text regions
        """
        preprocessed = self.preprocessor.preprocess(base64_image, resize=resize)
        result = self.ocr_engine.extract_text(preprocessed.image)

        # Scale coordinates back to original
        scaled_regions = self._scale_text_regions_to_original(
            result.text_regions,
            preprocessed.scale_factor
        )

        return OCRResult(
            text_regions=scaled_regions,
            processing_time_ms=result.processing_time_ms,
            language=result.language
        )

    def extract_text_fast(
        self,
        base64_image: str,
        resize: bool = True,
        max_width: int = 480,
        max_height: int = 270,
        use_header_roi: bool = False,
        header_roi_height: int = 250,
    ) -> OCRResult:
        """
        Fast OCR text extraction using RapidOCR, Windows OCR, or Tesseract.

        Performance optimizations:
        - RapidOCR (~200-400ms) - Default, 30-50% faster than Tesseract
        - Windows OCR (~50-200ms) - Fastest on Windows 10+
        - Header ROI (~60-70% faster) - Only OCR top portion where brand text is

        Use this for target verification (brand keyword matching) where speed
        is more important than accuracy.

        Args:
            base64_image: Base64 encoded image string
            resize: Whether to resize large images
            max_width: Maximum width for fast OCR
            max_height: Maximum height for fast OCR
            use_header_roi: If True, only OCR top portion (header area)
            header_roi_height: Height of header region to OCR (default 250px)

        Returns:
            OCRResult with text regions
        """
        from .fast_ocr_engine import get_fast_ocr_engine
        from app.config import settings

        start_time = time.perf_counter()

        # Get or create fast OCR engine (lazy loaded)
        fast_engine = get_fast_ocr_engine(settings)

        # Preprocess image
        preprocessed = self.preprocessor.preprocess(
            base64_image,
            resize=resize,
            max_width=max_width,
            max_height=max_height
        )
        preprocess_time = (time.perf_counter() - start_time) * 1000
        print(f"[FastOCR] Preprocess: {preprocess_time:.0f}ms, size: {preprocessed.processed_size}")

        # Run fast OCR (with optional header-only ROI)
        result = fast_engine.extract_text(
            preprocessed.image,
            use_roi=use_header_roi,
            roi_height=header_roi_height,
        )
        engine_info = fast_engine.get_engine_info()
        print(
            f"[FastOCR] {engine_info['backend']}: {result.processing_time_ms:.0f}ms, "
            f"regions: {len(result.text_regions)}, ROI: {use_header_roi}"
        )

        # Scale coordinates back to original
        scaled_regions = self._scale_text_regions_to_original(
            result.text_regions,
            preprocessed.scale_factor
        )

        return OCRResult(
            text_regions=scaled_regions,
            processing_time_ms=result.processing_time_ms,
            language=result.language
        )

    def _scale_elements_to_original(
        self,
        elements: List[UIElement],
        scale_factor: Tuple[float, float]
    ) -> List[UIElement]:
        """Scale element coordinates back to original image size."""
        if scale_factor == (1.0, 1.0):
            return elements

        scaled = []
        for elem in elements:
            scaled_bbox = self.preprocessor.scale_bbox_to_original(
                elem.bbox, scale_factor
            )
            scaled.append(UIElement(
                element_id=elem.element_id,
                element_type=elem.element_type,
                bbox=scaled_bbox,
                confidence=elem.confidence,
                label=elem.label,
                metadata=elem.metadata
            ))
        return scaled

    def _scale_text_regions_to_original(
        self,
        regions: List[TextRegion],
        scale_factor: Tuple[float, float]
    ) -> List[TextRegion]:
        """Scale text region coordinates back to original image size."""
        if scale_factor == (1.0, 1.0):
            return regions

        scaled = []
        for region in regions:
            scaled_bbox = self.preprocessor.scale_bbox_to_original(
                region.bbox, scale_factor
            )
            scaled.append(TextRegion(
                text=region.text,
                bbox=scaled_bbox,
                confidence=region.confidence,
                metadata=region.metadata
            ))
        return scaled

    def _fuse_labels_with_elements(
        self,
        elements: List[UIElement],
        text_regions: List[TextRegion]
    ) -> List[UIElement]:
        """
        Associate text labels with UI elements based on spatial proximity.

        Scoring:
        - Text inside element: score 1.0
        - Text overlapping element: score based on IoU
        - Text nearby element: score based on distance (up to 0.7)

        Args:
            elements: List of detected UI elements
            text_regions: List of OCR text regions

        Returns:
            Elements with labels assigned
        """
        labeled_elements = []

        for elem in elements:
            best_label = None
            best_score = 0.0

            for region in text_regions:
                score = self._calculate_association_score(elem.bbox, region.bbox)

                if score > best_score:
                    best_score = score
                    best_label = region.text

            # Only assign label if score is above threshold (lowered from 0.3 to 0.1 for better coverage)
            if best_score >= 0.1:
                labeled_elements.append(UIElement(
                    element_id=elem.element_id,
                    element_type=elem.element_type,
                    bbox=elem.bbox,
                    confidence=elem.confidence,
                    label=best_label,
                    metadata={
                        **elem.metadata,
                        "label_score": best_score
                    }
                ))
            else:
                labeled_elements.append(elem)

        return labeled_elements

    def _calculate_association_score(
        self,
        element_bbox: BoundingBox,
        text_bbox: BoundingBox
    ) -> float:
        """
        Calculate association score between element and text.

        Returns:
            Score from 0.0 to 1.0
        """
        # Check if text center is inside element
        text_center = text_bbox.center
        if element_bbox.contains_point(text_center[0], text_center[1]):
            return 1.0

        # Check overlap using IoU
        if element_bbox.overlaps(text_bbox):
            iou = element_bbox.iou(text_bbox)
            return 0.8 + (iou * 0.2)  # 0.8 to 1.0 based on IoU

        # Calculate distance-based score for nearby text
        elem_center = element_bbox.center
        text_center = text_bbox.center

        distance = ((elem_center[0] - text_center[0]) ** 2 +
                    (elem_center[1] - text_center[1]) ** 2) ** 0.5

        # Use element size as reference for "nearby" threshold
        reference_size = max(element_bbox.width, element_bbox.height)
        max_distance = reference_size * 4  # Consider text within 4x element size (increased from 2x)

        if distance < max_distance:
            # Linear falloff from 0.7 to 0.0 based on distance
            return 0.7 * (1 - distance / max_distance)

        # Even for far away text, return small score if within 200 pixels
        if distance < 200:
            return 0.1

        return 0.0

    def _print_timing_summary(
        self,
        timing: dict,
        detection_result: DetectionResult,
        ocr_result: OCRResult
    ) -> None:
        """Print a detailed timing summary box for debugging."""
        import sys

        # Get OCR backend name from engine info
        ocr_backend = "OCR"
        if hasattr(self, 'ocr_engine') and hasattr(self.ocr_engine, 'get_engine_info'):
            engine_info = self.ocr_engine.get_engine_info()
            ocr_backend = engine_info.get('engine', 'OCR')

        lines = [
            "",
            "=" * 70,
            "                    CV ANALYSIS TIMING BREAKDOWN",
            "=" * 70,
            f"  {'Component':<25} {'Time (ms)':<15} {'Details'}",
            "-" * 70,
            f"  {'Preprocessing':<25} {timing.get('preprocess', 0):>10.0f}ms",
            f"  {'Detection (OmniParser)':<25} {timing.get('detection', 0):>10.0f}ms    ({len(detection_result.elements)} elements)",
            f"  {f'OCR ({ocr_backend})':<25} {timing.get('ocr', 0):>10.0f}ms    ({len(ocr_result.text_regions)} text regions)",
            f"  {'Parallel Wall Time':<25} {timing.get('parallel_total', 0):>10.0f}ms",
            f"  {'Coordinate Scaling':<25} {timing.get('scaling', 0):>10.0f}ms",
            f"  {'Label Fusion':<25} {timing.get('fusion', 0):>10.0f}ms",
            "-" * 70,
            f"  {'TOTAL':<25} {timing.get('total', 0):>10.0f}ms",
            "=" * 70,
        ]

        # Highlight the bottleneck
        detection_time = timing.get('detection', 0)
        ocr_time = timing.get('ocr', 0)
        if detection_time > ocr_time:
            lines.append(f"  BOTTLENECK: Detection ({detection_time:.0f}ms) - {detection_time/timing.get('total', 1)*100:.1f}% of total")
        else:
            lines.append(f"  BOTTLENECK: OCR ({ocr_time:.0f}ms) - {ocr_time/timing.get('total', 1)*100:.1f}% of total")
        lines.append("=" * 70)
        lines.append("")

        # Print all at once and flush
        print("\n".join(lines), flush=True)
        sys.stdout.flush()

    def get_health_status(self) -> dict:
        """
        Get health status of all CV components.

        Returns:
            Dictionary with component health info
        """
        # Detect which type of detector is being used
        detector_info = self.detector.get_model_info()
        detector_type = detector_info.get("detector", "unknown")
        if hasattr(self.detector, 'icon_detect_path'):
            detector_type = "omniparser"
        elif hasattr(self.detector, 'model_path'):
            detector_type = "yolo"

        return {
            "detector": {
                "type": detector_type,
                **detector_info
            },
            "ocr_engine": self.ocr_engine.get_engine_info(),
            "preprocessor": {
                "max_size_mb": self.preprocessor.max_size_bytes / (1024 * 1024),
                "supported_formats": self.preprocessor.supported_formats
            }
        }


def create_context_engine_from_settings(settings) -> ContextEngine:
    """
    Factory function to create context engine from app settings.

    Uses OmniParser by default if available, falls back to YOLO.

    Args:
        settings: Application settings object

    Returns:
        Configured ContextEngine
    """
    import os

    # Check if fast mode is enabled for faster processing
    fast_mode = getattr(settings, 'CV_FAST_MODE', False)
    if fast_mode:
        fast_width = getattr(settings, 'CV_FAST_RESIZE_WIDTH', 640)
        # Calculate height maintaining 16:9 aspect ratio
        fast_height = int(fast_width * 9 / 16)
        resize_width = fast_width
        resize_height = fast_height
        print(f"[ContextEngine] Fast mode enabled: using {resize_width}x{resize_height} resolution")
    else:
        resize_width = settings.CV_DEFAULT_RESIZE_WIDTH
        resize_height = settings.CV_DEFAULT_RESIZE_HEIGHT
        print(f"[ContextEngine] Standard mode: using {resize_width}x{resize_height} resolution")

    preprocessor = ImagePreprocessor(
        max_size_mb=settings.CV_MAX_IMAGE_SIZE_MB,
        supported_formats=settings.CV_SUPPORTED_FORMATS,
        default_resize_width=resize_width,
        default_resize_height=resize_height
    )

    # Choose detector based on settings and availability
    detector = None
    if settings.CV_DETECTION_BACKEND == "omniparser":
        icon_detect_path = settings.OMNIPARSER_ICON_DETECT_PATH
        if os.path.exists(icon_detect_path):
            from .omniparser_detector import OmniParserDetector
            use_openvino = getattr(settings, 'OMNIPARSER_USE_OPENVINO', True)
            use_int8 = getattr(settings, 'OMNIPARSER_USE_INT8', False)
            detector = OmniParserDetector(
                icon_detect_path=settings.OMNIPARSER_ICON_DETECT_PATH,
                icon_caption_path=settings.OMNIPARSER_ICON_CAPTION_PATH,
                confidence_threshold=settings.OMNIPARSER_CONFIDENCE_THRESHOLD,
                iou_threshold=settings.OMNIPARSER_IOU_THRESHOLD,
                device="cuda" if settings.OCR_USE_GPU else "cpu",
                enable_captioning=settings.OMNIPARSER_ENABLE_CAPTIONING,
                use_openvino=use_openvino,
                use_int8=use_int8
            )
            model_type = "INT8" if use_int8 else ("FP16" if use_openvino else "PyTorch")
            print(f"Using OmniParser detector from {icon_detect_path} ({model_type})")
        else:
            print(f"OmniParser model not found at {icon_detect_path}, falling back to YOLO")

    # Fall back to YOLO if OmniParser not configured or not available
    if detector is None:
        detector = YOLODetector(
            model_path=settings.YOLO_MODEL_PATH,
            confidence_threshold=settings.YOLO_CONFIDENCE_THRESHOLD,
            iou_threshold=settings.YOLO_IOU_THRESHOLD,
            device="cuda" if settings.OCR_USE_GPU else "cpu"
        )
        print(f"Using YOLO detector: {settings.YOLO_MODEL_PATH}")

    # Select OCR engine based on settings
    # Note: Surya OCR is extremely slow on CPU (~8-15 min), only use with GPU
    ocr_backend = getattr(settings, 'OCR_BACKEND', 'paddleocr')
    ocr_engine = None
    debug_timing = getattr(settings, 'CV_DEBUG_TIMING', False)

    print(f"\n[ContextEngine] Initializing OCR engine: {ocr_backend}")

    # Try PaddleOCR first if explicitly requested (accurate, ~5-10s on CPU)
    if ocr_backend == "paddleocr":
        # Check if OpenVINO acceleration is enabled (default: True for faster inference)
        use_openvino = getattr(settings, 'PADDLEOCR_USE_OPENVINO', True)

        if use_openvino:
            try:
                from .openvino_ocr_engine import OpenVINOOCREngine
                openvino_device = getattr(settings, 'PADDLEOCR_OPENVINO_DEVICE', 'CPU')
                diagnostic_mode = getattr(settings, 'OCR_DIAGNOSTIC_MODE', False)
                max_regions = getattr(settings, 'OCR_MAX_REGIONS', 10)
                max_aspect_ratio = getattr(settings, 'OCR_MAX_ASPECT_RATIO', 10.0)
                inference_threads = getattr(settings, 'OCR_INFERENCE_THREADS', -1)
                ocr_engine = OpenVINOOCREngine(
                    language=settings.OCR_LANGUAGE,
                    confidence_threshold=settings.OCR_CONFIDENCE_THRESHOLD,
                    device=openvino_device,
                    max_regions=max_regions,
                    max_aspect_ratio=max_aspect_ratio,
                    diagnostic_mode=diagnostic_mode,
                    inference_threads=inference_threads,
                )
                diag_status = " [DIAGNOSTIC]" if diagnostic_mode else ""
                thread_status = f", threads={inference_threads}" if inference_threads != -1 else ""
                aspect_status = f", max_aspect={max_aspect_ratio}" if max_aspect_ratio > 0 else ""
                print(f"[ContextEngine] Using PaddleOCR with OpenVINO acceleration ({openvino_device}{thread_status}{aspect_status}){diag_status}")
            except ImportError as e:
                print(f"[ContextEngine] OpenVINO OCR not available: {e}, falling back to PaddleOCR...")
                use_openvino = False
            except Exception as e:
                print(f"[ContextEngine] Error loading OpenVINO OCR: {e}, falling back to PaddleOCR...")
                use_openvino = False

        if not use_openvino or ocr_engine is None:
            try:
                from .paddle_ocr_engine import PaddleOCREngine
                ocr_engine = PaddleOCREngine(
                    language=settings.OCR_LANGUAGE,
                    use_gpu=settings.OCR_USE_GPU,
                    confidence_threshold=settings.OCR_CONFIDENCE_THRESHOLD,
                    use_angle_cls=getattr(settings, 'PADDLEOCR_USE_ANGLE_CLS', False)
                )
                gpu_status = "GPU" if settings.OCR_USE_GPU else "CPU"
                print(f"[ContextEngine] Using PaddleOCR engine ({gpu_status}, language: {settings.OCR_LANGUAGE})")
            except ImportError as e:
                print(f"[ContextEngine] PaddleOCR not installed: {e}, trying fallback...")
            except Exception as e:
                print(f"[ContextEngine] Error loading PaddleOCR: {e}, trying fallback...")

    # Try Google Cloud Vision OCR (fast cloud-based, ~2-5s)
    if ocr_engine is None and ocr_backend == "google":
        try:
            from .google_ocr_engine import GoogleOCREngine
            api_key = getattr(settings, 'GOOGLE_CLOUD_API_KEY', '')
            if api_key:
                ocr_engine = GoogleOCREngine(
                    api_key=api_key,
                    language=settings.OCR_LANGUAGE,
                    confidence_threshold=settings.OCR_CONFIDENCE_THRESHOLD,
                )
                print(f"[ContextEngine] Using Google Cloud Vision OCR (~2-5s, cloud-based)")
            else:
                print("[ContextEngine] Google OCR selected but GOOGLE_CLOUD_API_KEY not set, trying fallback...")
        except ImportError as e:
            print(f"[ContextEngine] Google Cloud Vision not installed: {e}")
            print("[ContextEngine] Install with: pip install google-cloud-vision")
        except Exception as e:
            print(f"[ContextEngine] Error loading Google OCR: {e}, trying fallback...")

    # Try Windows OCR (fastest, good for clean UI text)
    if ocr_engine is None and (ocr_backend == "windows_ocr" or ocr_backend == "auto"):
        try:
            from .fast_ocr_engine import FastOCREngine, _check_windows_ocr_available
            if _check_windows_ocr_available():
                ocr_engine = FastOCREngine(
                    language="eng",
                    confidence_threshold=settings.OCR_CONFIDENCE_THRESHOLD,
                    prefer_windows_ocr=True,
                )
                print(f"[ContextEngine] Using Windows OCR engine - fastest (~100-300ms)")
            else:
                print("[ContextEngine] Windows OCR not available, trying fallback...")
        except ImportError as e:
            print(f"[ContextEngine] Windows OCR not installed: {e}, trying fallback...")
        except Exception as e:
            print(f"[ContextEngine] Error loading Windows OCR: {e}, trying fallback...")

    # Try Surya OCR (only if explicitly requested - very slow on CPU)
    if ocr_engine is None and ocr_backend == "surya":
        try:
            from .surya_ocr_engine import SuryaOCREngine
            surya_engine = SuryaOCREngine(
                language=settings.OCR_LANGUAGE,
                confidence_threshold=settings.OCR_CONFIDENCE_THRESHOLD,
            )
            if surya_engine.is_available():
                ocr_engine = surya_engine
                print(f"[ContextEngine] Using Surya OCR engine (language: {settings.OCR_LANGUAGE}) - WARNING: very slow on CPU!")
            else:
                print("[ContextEngine] Surya OCR not available, trying fallback...")
        except ImportError as e:
            print(f"[ContextEngine] Surya OCR not installed: {e}, trying fallback...")
        except Exception as e:
            print(f"[ContextEngine] Error loading Surya OCR: {e}, trying fallback...")

    # Try PaddleOCR as fallback for other backends
    if ocr_engine is None and ocr_backend in ["windows_ocr", "auto", "surya"]:
        try:
            from .paddle_ocr_engine import PaddleOCREngine
            ocr_engine = PaddleOCREngine(
                language=settings.OCR_LANGUAGE,
                use_gpu=settings.OCR_USE_GPU,
                confidence_threshold=settings.OCR_CONFIDENCE_THRESHOLD,
                use_angle_cls=getattr(settings, 'PADDLEOCR_USE_ANGLE_CLS', False)
            )
            print(f"[ContextEngine] Using PaddleOCR engine as fallback (language: {settings.OCR_LANGUAGE})")
        except ImportError as e:
            print(f"[ContextEngine] PaddleOCR not installed: {e}, trying EasyOCR fallback...")
        except Exception as e:
            print(f"[ContextEngine] Error loading PaddleOCR: {e}, trying EasyOCR fallback...")

    # Final fallback to EasyOCR
    if ocr_engine is None:
        ocr_engine = OCREngine(
            language=settings.OCR_LANGUAGE,
            use_gpu=settings.OCR_USE_GPU,
            confidence_threshold=settings.OCR_CONFIDENCE_THRESHOLD
        )
        print(f"[ContextEngine] Using EasyOCR engine (language: {settings.OCR_LANGUAGE}) - fallback")

    print(f"[ContextEngine] Debug timing enabled: {debug_timing}\n")

    return ContextEngine(
        preprocessor=preprocessor,
        detector=detector,
        ocr_engine=ocr_engine
    )
