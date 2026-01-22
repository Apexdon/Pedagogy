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
from app.schemas.guidance import (
    GenerateGuidanceRequest,
    GenerateGuidanceResponse,
    GuidanceSessionResponse,
    GuidanceSessionDetailResponse,
    GuidanceStepResponse,
    HaloTargetResponse,
    AdvanceStepRequest,
    AdvanceStepResponse,
    SkipStepRequest,
    GoToStepRequest,
    UpdateScreenRequest,
    SessionStateResponse,
    SessionListResponse,
    GuidanceHealthResponse,
)
from app.schemas.target_application import (
    TargetAppCreate,
    TargetAppUpdate,
    TargetAppResponse,
    TargetAppListResponse,
    TargetAppDeleteResponse,
    SetDefaultResponse,
    TargetAppSettingsResponse,
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
    # Guidance
    "GenerateGuidanceRequest",
    "GenerateGuidanceResponse",
    "GuidanceSessionResponse",
    "GuidanceSessionDetailResponse",
    "GuidanceStepResponse",
    "HaloTargetResponse",
    "AdvanceStepRequest",
    "AdvanceStepResponse",
    "SkipStepRequest",
    "GoToStepRequest",
    "UpdateScreenRequest",
    "SessionStateResponse",
    "SessionListResponse",
    "GuidanceHealthResponse",
    # Target Applications
    "TargetAppCreate",
    "TargetAppUpdate",
    "TargetAppResponse",
    "TargetAppListResponse",
    "TargetAppDeleteResponse",
    "SetDefaultResponse",
    "TargetAppSettingsResponse",
]
