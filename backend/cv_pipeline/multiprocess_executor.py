"""
Multiprocessing Executor for CV Pipeline

Uses separate processes for YOLO detection and OCR to eliminate CPU contention.
Each process has its own memory space, preventing cache thrashing and memory
bandwidth competition.

Architecture:
- Main process: Coordinates requests, handles IPC
- YOLO worker process: Dedicated to UI element detection
- OCR worker process: Dedicated to text recognition

IPC Strategy:
- Uses multiprocessing.Queue for task coordination
- Uses shared memory (multiprocessing.Array) for zero-copy image transfer
- Results serialized via pickle (small overhead for result data)

Performance Notes:
- First request has ~500ms overhead for process spawn + model load
- Subsequent requests avoid model loading (workers stay alive)
- IPC overhead: ~50-100ms per request (serialize/deserialize)
- Expected benefit: Each task runs at full speed without contention
"""

import time
import pickle
import numpy as np
from multiprocessing import Process, Queue, Array, Event
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
import ctypes


@dataclass
class TaskResult:
    """Result from a worker process."""
    success: bool
    data: Any
    error: Optional[str]
    duration_ms: float


class SharedImageBuffer:
    """
    Shared memory buffer for zero-copy image transfer between processes.

    Allocates a fixed-size buffer that can hold images up to max_size.
    The main process writes image data, workers read it directly.
    """

    def __init__(self, max_width: int = 1920, max_height: int = 1080, channels: int = 3):
        """Initialize shared buffer for images up to max dimensions."""
        self.max_width = max_width
        self.max_height = max_height
        self.channels = channels
        self.max_size = max_width * max_height * channels

        # Shared array for image data (using ctypes for raw bytes)
        self._buffer = Array(ctypes.c_uint8, self.max_size, lock=False)

        # Shared values for current image dimensions
        self._width = Array(ctypes.c_int, 1, lock=False)
        self._height = Array(ctypes.c_int, 1, lock=False)

    def write_image(self, image: np.ndarray) -> bool:
        """
        Write image to shared buffer.

        Returns False if image too large for buffer.
        """
        h, w, c = image.shape
        size = h * w * c

        if size > self.max_size:
            return False

        # Write dimensions
        self._width[0] = w
        self._height[0] = h

        # Write image data (flatten and copy to shared buffer)
        flat = image.flatten()
        self._buffer[:size] = flat

        return True

    def read_image(self) -> np.ndarray:
        """Read image from shared buffer."""
        w = self._width[0]
        h = self._height[0]
        size = h * w * self.channels

        # Read from buffer and reshape
        flat = np.array(self._buffer[:size], dtype=np.uint8)
        return flat.reshape((h, w, self.channels))


def _yolo_worker(
    task_queue: Queue,
    result_queue: Queue,
    ready_event: Event,
    shutdown_event: Event,
    shared_buffer: SharedImageBuffer
):
    """
    Worker process for YOLO detection.

    Loads model once, then processes tasks from queue until shutdown.
    """
    import os
    import sys
    from pathlib import Path

    # Ensure correct working directory (subprocess may inherit different cwd)
    backend_dir = Path(__file__).parent.parent.resolve()
    os.chdir(backend_dir)
    print(f"[YOLO Worker] Working directory: {backend_dir}", flush=True)

    # Set thread limits for this process (full CPU usage since isolated)
    threads = os.environ.get('CV_MULTIPROC_THREADS', '8')
    os.environ['OMP_NUM_THREADS'] = threads
    os.environ['MKL_NUM_THREADS'] = threads

    print(f"[YOLO Worker] Starting with {threads} threads...", flush=True)

    try:
        # Import and load model using absolute paths
        from cv_pipeline.omniparser_detector import OmniParserDetector

        model_path = str(backend_dir / "weights" / "icon_detect" / "model.pt")
        caption_path = str(backend_dir / "weights" / "icon_caption_florence")

        print(f"[YOLO Worker] Loading model from: {model_path}", flush=True)

        detector = OmniParserDetector(
            icon_detect_path=model_path,
            icon_caption_path=caption_path,
            confidence_threshold=0.25,
            device="cpu",
            enable_captioning=False,  # Disable captioning for speed
            use_openvino=True,  # Use OpenVINO for 3-4x faster CPU inference
            use_int8=True  # Use INT8 quantized model for 2-4x faster inference
        )

        # Warm up model (OpenVINO JIT compilation can take 60+ seconds)
        print("[YOLO Worker] Starting warmup (may take 60+ seconds for OpenVINO JIT)...", flush=True)
        dummy = np.zeros((360, 640, 3), dtype=np.uint8)
        detector.detect(dummy, generate_captions=False)

        print("[YOLO Worker] Model loaded and warmed up", flush=True)
        ready_event.set()

        # Process loop
        while not shutdown_event.is_set():
            try:
                # Wait for task with timeout (allows checking shutdown)
                task = task_queue.get(timeout=0.5)

                if task is None:  # Shutdown signal
                    break

                task_id, use_shared_mem = task
                start = time.perf_counter()

                try:
                    # Read image from shared memory or queue
                    if use_shared_mem:
                        image = shared_buffer.read_image()
                    else:
                        # Image was pickled in task
                        image = task[2]

                    # Run detection
                    elements = detector.detect(image, generate_captions=False)

                    duration = (time.perf_counter() - start) * 1000

                    # Serialize result
                    result = TaskResult(
                        success=True,
                        data=elements,
                        error=None,
                        duration_ms=duration
                    )

                except Exception as e:
                    duration = (time.perf_counter() - start) * 1000
                    result = TaskResult(
                        success=False,
                        data=None,
                        error=str(e),
                        duration_ms=duration
                    )

                result_queue.put((task_id, result))

            except Exception:
                # Queue.get timeout - continue loop
                continue

    except Exception as e:
        import traceback
        print(f"[YOLO Worker] Fatal error: {e}", flush=True)
        traceback.print_exc()
        ready_event.set()  # Unblock main process

    print("[YOLO Worker] Shutting down", flush=True)


def _ocr_worker(
    task_queue: Queue,
    result_queue: Queue,
    ready_event: Event,
    shutdown_event: Event,
    shared_buffer: SharedImageBuffer,
    diagnostic_mode: bool = False
):
    """
    Worker process for OCR.

    Loads model once, then processes tasks from queue until shutdown.
    """
    import os

    # Set thread limits for this process
    threads = os.environ.get('CV_MULTIPROC_THREADS', '8')
    os.environ['OMP_NUM_THREADS'] = threads
    os.environ['MKL_NUM_THREADS'] = threads
    os.environ['OV_CPU_NUM_THREADS'] = threads

    print(f"[OCR Worker] Starting with {threads} threads, diagnostic_mode={diagnostic_mode}...")

    try:
        # Import and load model
        from cv_pipeline.openvino_ocr_engine import OpenVINOOCREngine
        # Use the thread count from environment (already set above)
        inference_threads = int(threads) if threads != '-1' else -1
        # Get max_aspect_ratio from environment (default: 10.0)
        max_aspect_ratio = float(os.environ.get('OCR_MAX_ASPECT_RATIO', '10.0'))
        ocr_engine = OpenVINOOCREngine(
            language="en",
            confidence_threshold=0.5,
            max_regions=10,
            max_aspect_ratio=max_aspect_ratio,
            diagnostic_mode=diagnostic_mode,
            inference_threads=inference_threads,
        )

        # Warm up model
        dummy = np.zeros((360, 640, 3), dtype=np.uint8)
        ocr_engine.extract_text(dummy)

        print("[OCR Worker] Model loaded and warmed up")
        ready_event.set()

        # Process loop
        while not shutdown_event.is_set():
            try:
                task = task_queue.get(timeout=0.5)

                if task is None:
                    break

                task_id, use_shared_mem = task[:2]
                start = time.perf_counter()

                try:
                    if use_shared_mem:
                        image = shared_buffer.read_image()
                    else:
                        image = task[2]

                    # Run OCR
                    ocr_result = ocr_engine.extract_text(image)

                    duration = (time.perf_counter() - start) * 1000

                    result = TaskResult(
                        success=True,
                        data=ocr_result,
                        error=None,
                        duration_ms=duration
                    )

                except Exception as e:
                    duration = (time.perf_counter() - start) * 1000
                    result = TaskResult(
                        success=False,
                        data=None,
                        error=str(e),
                        duration_ms=duration
                    )

                result_queue.put((task_id, result))

            except Exception:
                continue

    except Exception as e:
        print(f"[OCR Worker] Fatal error: {e}")
        ready_event.set()

    print("[OCR Worker] Shutting down")


class MultiprocessExecutor:
    """
    Manages worker processes for parallel CV analysis.

    Usage:
        executor = MultiprocessExecutor()
        executor.start()

        # Run tasks in parallel
        yolo_result, ocr_result = executor.run_parallel(image)

        executor.shutdown()
    """

    def __init__(self, use_shared_memory: bool = True, diagnostic_mode: bool = False):
        """
        Initialize executor.

        Args:
            use_shared_memory: If True, use shared memory for image transfer.
                             If False, pickle images through queues (slower).
            diagnostic_mode: If True, enable per-region OCR timing capture.
        """
        self.use_shared_memory = use_shared_memory
        self.diagnostic_mode = diagnostic_mode

        # Shared memory buffer
        self._shared_buffer = SharedImageBuffer() if use_shared_memory else None

        # Worker processes
        self._yolo_process: Optional[Process] = None
        self._ocr_process: Optional[Process] = None

        # Communication queues
        self._yolo_task_queue: Optional[Queue] = None
        self._yolo_result_queue: Optional[Queue] = None
        self._ocr_task_queue: Optional[Queue] = None
        self._ocr_result_queue: Optional[Queue] = None

        # Synchronization
        self._yolo_ready = Event()
        self._ocr_ready = Event()
        self._shutdown = Event()

        self._started = False
        self._task_counter = 0

    def start(self, timeout: float = 120.0) -> bool:
        """
        Start worker processes and wait for them to be ready.

        Args:
            timeout: Max seconds to wait for workers to initialize.
                     OpenVINO JIT compilation can take 60-90 seconds on first run.

        Returns:
            True if both workers started successfully
        """
        if self._started:
            return True

        print("[MultiprocessExecutor] Starting worker processes...")
        start_time = time.perf_counter()

        # Create queues
        self._yolo_task_queue = Queue()
        self._yolo_result_queue = Queue()
        self._ocr_task_queue = Queue()
        self._ocr_result_queue = Queue()

        # Start YOLO worker
        self._yolo_process = Process(
            target=_yolo_worker,
            args=(
                self._yolo_task_queue,
                self._yolo_result_queue,
                self._yolo_ready,
                self._shutdown,
                self._shared_buffer
            ),
            daemon=True
        )
        self._yolo_process.start()

        # Start OCR worker
        self._ocr_process = Process(
            target=_ocr_worker,
            args=(
                self._ocr_task_queue,
                self._ocr_result_queue,
                self._ocr_ready,
                self._shutdown,
                self._shared_buffer,
                self.diagnostic_mode
            ),
            daemon=True
        )
        self._ocr_process.start()

        # Wait for both workers to be ready
        yolo_ready = self._yolo_ready.wait(timeout=timeout)
        ocr_ready = self._ocr_ready.wait(timeout=timeout)

        if not yolo_ready or not ocr_ready:
            print("[MultiprocessExecutor] Worker startup timeout!")
            self.shutdown()
            return False

        elapsed = (time.perf_counter() - start_time) * 1000
        print(f"[MultiprocessExecutor] Workers ready in {elapsed:.0f}ms")

        self._started = True
        return True

    def run_parallel(
        self,
        image: np.ndarray
    ) -> Tuple[Optional[List], Optional[Any], Dict[str, float]]:
        """
        Run YOLO detection and OCR in parallel using separate processes.

        Args:
            image: BGR numpy array

        Returns:
            Tuple of (yolo_elements, ocr_result, timing_dict)
        """
        if not self._started:
            raise RuntimeError("Executor not started. Call start() first.")

        timing = {
            'ipc_write_ms': 0,
            'yolo_ms': 0,
            'ocr_ms': 0,
            'ipc_read_ms': 0,
            'wall_ms': 0
        }

        wall_start = time.perf_counter()

        # Generate task IDs
        self._task_counter += 1
        yolo_task_id = f"yolo_{self._task_counter}"
        ocr_task_id = f"ocr_{self._task_counter}"

        # Write image to shared memory or prepare for pickling
        ipc_start = time.perf_counter()

        if self.use_shared_memory and self._shared_buffer:
            if not self._shared_buffer.write_image(image):
                raise ValueError(f"Image too large for shared buffer: {image.shape}")

            # Send task with flag to use shared memory
            self._yolo_task_queue.put((yolo_task_id, True))
            self._ocr_task_queue.put((ocr_task_id, True))
        else:
            # Pickle image in task (slower)
            self._yolo_task_queue.put((yolo_task_id, False, image))
            self._ocr_task_queue.put((ocr_task_id, False, image))

        timing['ipc_write_ms'] = (time.perf_counter() - ipc_start) * 1000

        # Wait for results
        read_start = time.perf_counter()

        yolo_result = None
        ocr_result = None

        # Collect results (order may vary)
        results_received = 0
        while results_received < 2:
            # Check YOLO result
            try:
                task_id, result = self._yolo_result_queue.get(timeout=0.1)
                if task_id == yolo_task_id:
                    yolo_result = result
                    timing['yolo_ms'] = result.duration_ms
                    results_received += 1
            except:
                pass

            # Check OCR result
            try:
                task_id, result = self._ocr_result_queue.get(timeout=0.1)
                if task_id == ocr_task_id:
                    ocr_result = result
                    timing['ocr_ms'] = result.duration_ms
                    results_received += 1
            except:
                pass

        timing['ipc_read_ms'] = (time.perf_counter() - read_start) * 1000
        timing['wall_ms'] = (time.perf_counter() - wall_start) * 1000

        # Extract data from results
        elements = yolo_result.data if yolo_result and yolo_result.success else []
        ocr_data = ocr_result.data if ocr_result and ocr_result.success else None

        # Log any errors
        if yolo_result and not yolo_result.success:
            print(f"[MultiprocessExecutor] YOLO error: {yolo_result.error}")
        if ocr_result and not ocr_result.success:
            print(f"[MultiprocessExecutor] OCR error: {ocr_result.error}")

        return elements, ocr_data, timing

    def shutdown(self):
        """Stop worker processes gracefully."""
        if not self._started:
            return

        print("[MultiprocessExecutor] Shutting down workers...")

        # Signal shutdown
        self._shutdown.set()

        # Send None to unblock workers waiting on queues
        if self._yolo_task_queue:
            self._yolo_task_queue.put(None)
        if self._ocr_task_queue:
            self._ocr_task_queue.put(None)

        # Wait for processes to terminate
        if self._yolo_process and self._yolo_process.is_alive():
            self._yolo_process.join(timeout=5.0)
            if self._yolo_process.is_alive():
                self._yolo_process.terminate()

        if self._ocr_process and self._ocr_process.is_alive():
            self._ocr_process.join(timeout=5.0)
            if self._ocr_process.is_alive():
                self._ocr_process.terminate()

        self._started = False
        print("[MultiprocessExecutor] Shutdown complete")

    def is_running(self) -> bool:
        """Check if workers are running."""
        return self._started and \
               self._yolo_process is not None and self._yolo_process.is_alive() and \
               self._ocr_process is not None and self._ocr_process.is_alive()


# Global executor instance (lazy initialized)
_global_executor: Optional[MultiprocessExecutor] = None


def get_multiprocess_executor() -> MultiprocessExecutor:
    """Get or create the global multiprocess executor."""
    global _global_executor

    if _global_executor is None:
        # Read diagnostic mode from settings
        try:
            from app.config import settings
            diagnostic_mode = getattr(settings, 'OCR_DIAGNOSTIC_MODE', False)
        except ImportError:
            diagnostic_mode = False

        _global_executor = MultiprocessExecutor(
            use_shared_memory=True,
            diagnostic_mode=diagnostic_mode
        )

    return _global_executor


def shutdown_multiprocess_executor():
    """Shutdown the global executor if running."""
    global _global_executor

    if _global_executor is not None:
        _global_executor.shutdown()
        _global_executor = None
