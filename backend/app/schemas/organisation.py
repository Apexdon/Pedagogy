"""
Organisation Schemas

Pydantic models for organisation requests and responses.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime


class OrganisationCreate(BaseModel):
    """Schema for creating an organisation."""
    org_name: str = Field(..., min_length=1, max_length=255)
    org_slug: str = Field(..., min_length=1, max_length=100, pattern="^[a-z0-9-]+$")
    primary_color: Optional[str] = Field("#3B82F6", pattern="^#[0-9A-Fa-f]{6}$")


class BrandingConfig(BaseModel):
    """Schema for organisation branding."""
    primary_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    logo_base64: Optional[str] = None


class SettingsConfig(BaseModel):
    """Schema for organisation default settings."""
    hotkey: str = "Ctrl+Shift+P"
    auto_capture_on_query: bool = False
    default_language: str = "en"


class InitialUser(BaseModel):
    """Schema for initial user during onboarding."""
    email: EmailStr
    role: str = Field("user", pattern="^(org_admin|manager|user|viewer)$")


class OrganisationOnboard(BaseModel):
    """Schema for organisation onboarding."""
    org_name: str = Field(..., min_length=1, max_length=255)
    org_slug: str = Field(..., min_length=1, max_length=100, pattern="^[a-z0-9-]+$")
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=8)
    admin_name: str = Field(..., min_length=1, max_length=255)
    branding: Optional[BrandingConfig] = None
    settings: Optional[SettingsConfig] = None
    initial_users: Optional[List[InitialUser]] = None


class OrganisationResponse(BaseModel):
    """Schema for organisation response."""
    org_id: str
    org_name: str
    org_slug: str
    logo_path: Optional[str] = None
    primary_color: str
    subscription_tier: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class KnowledgeBaseInfo(BaseModel):
    """Schema for knowledge base summary."""
    kb_id: str
    kb_name: str
    document_count: int
    step_count: int


class OrganisationStats(BaseModel):
    """Schema for organisation statistics."""
    total_users: int
    total_sessions: int
    last_activity: Optional[datetime] = None


class OrganisationProfile(BaseModel):
    """Schema for full organisation profile."""
    org_id: str
    org_name: str
    org_slug: str
    logo_path: Optional[str] = None
    primary_color: str
    branding: Dict[str, Any] = {}
    settings: Dict[str, Any] = {}
    knowledge_bases: List[KnowledgeBaseInfo] = []
    stats: OrganisationStats

    class Config:
        from_attributes = True


class OnboardingStatus(BaseModel):
    """Schema for onboarding status check."""
    org_id: str
    org_name: str
    onboarding_status: str  # pending, in_progress, completed
    checklist: Dict[str, bool]
    completion_percentage: int
    pending_items: List[str]


class OnboardingResponse(BaseModel):
    """Schema for onboarding completion response."""
    success: bool = True
    organisation: OrganisationResponse
    admin_user: Dict[str, Any]
    users_invited: int = 0
    next_steps: List[str] = []


class AddMemberRequest(BaseModel):
    """Schema for adding a member to an organisation."""
    email: EmailStr
    role: str = Field("user", pattern="^(org_admin|manager|user|viewer)$")


class MemberResponse(BaseModel):
    """Schema for member info response."""
    user_id: str
    email: str
    full_name: Optional[str] = None
    role: str
    joined_at: datetime


class AddMemberResponse(BaseModel):
    """Schema for add member response."""
    success: bool = True
    message: str
    member: Optional[MemberResponse] = None


class OrganisationListItem(BaseModel):
    """Schema for organisation list item (public info)."""
    org_id: str
    org_name: str
    org_slug: str
    primary_color: str

    class Config:
        from_attributes = True
