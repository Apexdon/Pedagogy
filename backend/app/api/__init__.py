"""
Pedagogy API Routes

FastAPI routers for all API endpoints.
"""

from fastapi import APIRouter
from app.api import auth, organisations, knowledge

# Create main API router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(organisations.router, prefix="/org", tags=["Organisation"])
api_router.include_router(knowledge.router, prefix="/org", tags=["Knowledge Base"])
