"""
Pedagogy API Routes

FastAPI routers for all API endpoints.
"""

from fastapi import APIRouter
from app.api import auth, organisations, knowledge, cv_analysis

# Create main API router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(organisations.router, prefix="/org", tags=["Organisation"])
api_router.include_router(knowledge.router, prefix="/org", tags=["Knowledge Base"])
api_router.include_router(cv_analysis.router, tags=["Computer Vision"])
