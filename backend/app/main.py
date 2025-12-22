"""
Pedagogy Backend - Main Application

FastAPI application entry point with health check endpoints.
"""

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
    # Startup: Initialize database tables
    await init_db()
    print("Database tables initialized")
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
