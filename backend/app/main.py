"""
Pedagogy Backend - Main Application

FastAPI application entry point with health check endpoints.
"""

# CRITICAL: Import preload FIRST before ANY other imports
# This sets environment variables needed by PaddleOCR/PaddleX
from app import preload  # noqa: F401 - side effects only

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db, init_db
from app.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - runs on startup and shutdown."""
    import time
    import numpy as np

    # Startup: Reset CV service to force fresh initialization
    # This is critical for uvicorn --reload to pick up code changes
    from app.services.cv_service import reset_cv_service
    reset_cv_service()
    print("[Startup] CV service reset - will reinitialize with latest code")

    # Reset OmniParser global model cache
    try:
        from cv_pipeline import omniparser_detector
        omniparser_detector._icon_detect_model = None
        omniparser_detector._icon_caption_model = None
        omniparser_detector._icon_caption_processor = None
        print("[Startup] OmniParser model cache cleared")
    except ImportError:
        pass

    # Initialize database tables
    await init_db()
    print("Database tables initialized")

    # =========================================
    # PRELOAD CV MODELS (eliminates first-run delay)
    # =========================================
    # Models use lazy loading - preload them now so first user request is fast
    # OPTIMIZATION: Use realistic image size (640x360) and multiple warmup runs
    # to fully warm CPU caches and any JIT compilation
    print("\n" + "=" * 60)
    print("  PRELOADING CV MODELS (this may take 10-15 seconds)...")
    print("=" * 60)

    preload_start = time.perf_counter()

    # Number of warmup iterations (first loads model, subsequent warm caches)
    WARMUP_ITERATIONS = 3

    try:
        from app.services.cv_service import get_cv_service
        cv_service = get_cv_service()

        # Set PyTorch thread limit (must be done after torch is imported via cv_service)
        try:
            import torch
            import os
            threads = int(os.environ.get('CV_THREADS_PER_TASK', '4'))
            torch.set_num_threads(threads)
            print(f"  [Thread Limit] PyTorch threads set to {threads}", flush=True)
        except Exception as e:
            print(f"  [Thread Limit] Could not set PyTorch threads: {e}", flush=True)

        # Create a realistic-sized dummy image matching fast mode (640x360)
        # This ensures warmup exercises the same code paths as real usage
        warmup_width = settings.CV_FAST_RESIZE_WIDTH if settings.CV_FAST_MODE else settings.CV_DEFAULT_RESIZE_WIDTH
        warmup_height = 360 if settings.CV_FAST_MODE else settings.CV_DEFAULT_RESIZE_HEIGHT
        dummy_image = np.zeros((warmup_height, warmup_width, 3), dtype=np.uint8)

        # Add some noise to make it more realistic (helps with edge detection)
        dummy_image = np.random.randint(50, 200, (warmup_height, warmup_width, 3), dtype=np.uint8)

        print(f"  Warmup image size: {warmup_width}x{warmup_height} ({WARMUP_ITERATIONS} iterations)", flush=True)

        # Warmup detector (loads YOLO/OmniParser model)
        print(f"  [Detector] Running {WARMUP_ITERATIONS} warmup iterations...", flush=True)
        detector_times = []
        try:
            for i in range(WARMUP_ITERATIONS):
                iter_start = time.perf_counter()
                _ = cv_service.context_engine.detector.detect(dummy_image, generate_captions=False)
                iter_time = (time.perf_counter() - iter_start) * 1000
                detector_times.append(iter_time)
                print(f"    Detector iteration {i+1}: {iter_time:.0f}ms", flush=True)
            print(f"  [OK] Detector warmed: {detector_times[0]:.0f}ms -> {detector_times[-1]:.0f}ms", flush=True)
        except Exception as e:
            print(f"  [!] Detector warmup failed: {e}", flush=True)

        # Warmup OCR engine (loads OpenVINO/PaddleOCR model)
        print(f"  [OCR] Running {WARMUP_ITERATIONS} warmup iterations...", flush=True)
        ocr_times = []
        try:
            for i in range(WARMUP_ITERATIONS):
                iter_start = time.perf_counter()
                _ = cv_service.context_engine.ocr_engine.extract_text(dummy_image)
                iter_time = (time.perf_counter() - iter_start) * 1000
                ocr_times.append(iter_time)
                print(f"    OCR iteration {i+1}: {iter_time:.0f}ms", flush=True)
            print(f"  [OK] OCR warmed: {ocr_times[0]:.0f}ms -> {ocr_times[-1]:.0f}ms", flush=True)
        except Exception as e:
            print(f"  [!] OCR warmup failed: {e}", flush=True)

        preload_time = (time.perf_counter() - preload_start) * 1000
        print("=" * 60, flush=True)
        print(f"  CV MODELS PRELOADED in {preload_time:.0f}ms", flush=True)
        print("  First user request will now be fast!", flush=True)
        print("=" * 60 + "\n", flush=True)

    except Exception as e:
        print(f"  [!] CV model preload failed: {e}")
        print("  First request will load models (slower)")
        print("=" * 60 + "\n")

    yield
    # Shutdown: Cleanup if needed
    print("Application shutting down")


# Create FastAPI application
app = FastAPI(
    title="Pedagogy API",
    description="AI Desktop Assistant Backend",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "debug": settings.DEBUG
    }


@app.get("/health/db")
async def database_health(db: AsyncSession = Depends(get_db)):
    """Database health check endpoint."""
    try:
        result = await db.execute(text("SELECT 1"))
        result.fetchone()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


@app.get("/health/services")
async def services_health(db: AsyncSession = Depends(get_db)):
    """Detailed services health check."""
    from app.services.cv_service import get_cv_service

    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    # Check CV pipeline status
    cv_status = "ready"
    try:
        cv_service = get_cv_service()
        cv_health = await cv_service.get_health_status()
        cv_status = cv_health.status
    except Exception:
        cv_status = "unhealthy"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "services": {
            "api": {"status": "healthy"},
            "database": {"status": db_status},
            "vector_db": {"status": "ready"},
            "cv_pipeline": {"status": cv_status},
            "ai_engine": {"status": "pending_setup"}
        }
    }


# Entry point for running with `python -m app.main`
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
