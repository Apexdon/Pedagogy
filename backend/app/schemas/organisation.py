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


class RecentActivityItem(BaseModel):
    """Schema for a recent activity item."""
    activity_id: str
    activity_type: str  # member_joined, document_uploaded, session_completed, etc.
    description: str
    timestamp: datetime
    user_name: Optional[str] = None
    metadata: Dict[str, Any] = {}


class TeamMemberSummary(BaseModel):
    """Schema for team member summary in dashboard."""
    user_id: str
    full_name: Optional[str] = None
    email: str
    role: str
    joined_at: datetime


class KnowledgeBaseSummary(BaseModel):
    """Schema for knowledge base summary in dashboard."""
    total_documents: int
    total_chunks: int
    recent_uploads: List[Dict[str, Any]] = []
    processing_status: Dict[str, int] = {}  # pending, processing, completed, failed counts


class OrgDashboardStats(BaseModel):
    """Schema for org admin dashboard statistics."""
    # Overview stats
    total_members: int
    total_documents: int
    total_sessions: int
    total_knowledge_bases: int

    # Onboarding progress
    onboarding_completion: int  # percentage
    pending_setup_items: List[str] = []

    # Recent activity
    recent_activities: List[RecentActivityItem] = []

    # Team overview
    team_members: List[TeamMemberSummary] = []
    members_by_role: Dict[str, int] = {}  # role -> count

    # Knowledge base summary
    knowledge_base: KnowledgeBaseSummary

    # Analytics preview (placeholders for now)
    sessions_this_week: int = 0
    sessions_trend: str = "stable"  # up, down, stable


class UpdateProfileRequest(BaseModel):
    """Schema for updating organisation profile."""
    org_name: Optional[str] = Field(None, min_length=1, max_length=255)
    primary_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")


class UpdateProfileResponse(BaseModel):
    """Schema for update profile response."""
    success: bool = True
    message: str
    organisation: OrganisationResponse
