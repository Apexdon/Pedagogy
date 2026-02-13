"""
Preload Module - Sets critical environment variables BEFORE any imports.

This module MUST be imported FIRST in main.py before any other imports,
especially before anything that might import paddlex/paddleocr.

The PaddleX connectivity check adds 10-60 seconds on first load if not disabled.
"""

import os

# =========================================
# THREAD LIMITING FOR PARALLEL EXECUTION
# =========================================
# When running YOLO detection and OCR in parallel, both try to use all CPU cores.
# This causes severe CPU contention, making each task ~2x slower.
# Solution: Limit threads per task so they don't fight over cores.
#
# With 2 parallel tasks, each should use roughly half the available cores.
# Setting to 4 threads is a good balance for most systems.
# Set CV_THREADS_PER_TASK env var to override (e.g., "2" for low-end CPUs)

THREADS_PER_TASK = os.environ.get('CV_THREADS_PER_TASK', '4')

# OpenMP threads (used by PyTorch, OpenVINO, NumPy, etc.)
os.environ['OMP_NUM_THREADS'] = THREADS_PER_TASK

# Intel MKL threads (used by NumPy, PyTorch on Intel CPUs)
os.environ['MKL_NUM_THREADS'] = THREADS_PER_TASK

# OpenBLAS threads (alternative to MKL)
os.environ['OPENBLAS_NUM_THREADS'] = THREADS_PER_TASK

# NumExpr threads
os.environ['NUMEXPR_NUM_THREADS'] = THREADS_PER_TASK

# OpenVINO specific thread control
os.environ['OV_CPU_NUM_THREADS'] = THREADS_PER_TASK

print(f"[Preload] Thread limiting: {THREADS_PER_TASK} threads per task (set CV_THREADS_PER_TASK to override)")

# =========================================
# PADDLEOCR OPTIMIZATIONS
# =========================================
# Disable PaddleOCR/PaddleX connectivity check (adds significant delay)
os.environ['DISABLE_MODEL_SOURCE_CHECK'] = 'True'

# Also try the Paddle-style env var (GFLAGS format)
os.environ['FLAGS_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

# Suppress PaddlePaddle verbose logging
os.environ['GLOG_minloglevel'] = '2'

# Disable PaddlePaddle eager initialization which can slow startup
os.environ['FLAGS_eager_delete_tensor_gb'] = '0'

print("[Preload] Environment variables set for PaddleOCR optimization")
