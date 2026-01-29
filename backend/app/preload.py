"""
Preload Module - Sets critical environment variables BEFORE any imports.

This module MUST be imported FIRST in main.py before any other imports,
especially before anything that might import paddlex/paddleocr.

The PaddleX connectivity check adds 10-60 seconds on first load if not disabled.
"""

import os

# Disable PaddleOCR/PaddleX connectivity check (adds significant delay)
os.environ['DISABLE_MODEL_SOURCE_CHECK'] = 'True'

# Also try the Paddle-style env var (GFLAGS format)
os.environ['FLAGS_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

# Suppress PaddlePaddle verbose logging
os.environ['GLOG_minloglevel'] = '2'

# Disable PaddlePaddle eager initialization which can slow startup
os.environ['FLAGS_eager_delete_tensor_gb'] = '0'

print("[Preload] Environment variables set for PaddleOCR optimization")
