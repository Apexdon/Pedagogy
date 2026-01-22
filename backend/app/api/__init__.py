"""
Pedagogy API Routes

FastAPI routers for all API endpoints.
"""

from fastapi import APIRouter
from app.api import auth, organisations, knowledge, cv_analysis, guidance, target_applications

# Create main API router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(organisations.router, prefix="/org", tags=["Organisation"])
api_router.include_router(knowledge.router, prefix="/org", tags=["Knowledge Base"])
api_router.include_router(target_applications.router, prefix="/target-apps", tags=["Target Applications"])
api_router.include_router(cv_analysis.router, tags=["Computer Vision"])
api_router.include_router(guidance.router, tags=["AI Guidance"])
