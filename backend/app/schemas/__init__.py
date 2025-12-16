"""
Pedagogy Pydantic Schemas

Request/Response schemas for API validation.
"""

from app.schemas.auth import (
    UserRegister,
    UserLogin,
    Token,
    TokenPayload,
    UserResponse,
)
from app.schemas.organisation import (
    OrganisationCreate,
    OrganisationOnboard,
    OrganisationResponse,
    OrganisationProfile,
)

__all__ = [
    "UserRegister",
    "UserLogin",
    "Token",
    "TokenPayload",
    "UserResponse",
    "OrganisationCreate",
    "OrganisationOnboard",
    "OrganisationResponse",
    "OrganisationProfile",
]
