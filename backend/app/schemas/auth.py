"""
Authentication Schemas

Pydantic models for authentication requests and responses.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


class UserRegister(BaseModel):
    """Schema for user registration.

    Users register independently without being tied to an organisation.
    After registration, they can join organisations or be invited to them.
    """
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    full_name: str = Field(..., min_length=1, max_length=255)


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class SelectOrganisation(BaseModel):
    """Schema for selecting an organisation after login."""
    org_id: str = Field(..., description="Organisation ID to select")


class Token(BaseModel):
    """Schema for authentication tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(..., description="Token expiry in seconds")


class TokenPayload(BaseModel):
    """Schema for JWT token payload."""
    sub: str  # user_id
    org_id: Optional[str] = None  # May be None if no org selected
    role: Optional[str] = None  # Role within selected org
    exp: int


class UserResponse(BaseModel):
    """Schema for user response (without org-specific fields)."""
    user_id: str
    email: str
    full_name: Optional[str] = None
    is_active: bool
    email_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrganisationBasic(BaseModel):
    """Basic organisation info for user responses."""
    org_id: str
    org_name: str
    org_slug: str

    class Config:
        from_attributes = True


class UserOrganisationInfo(BaseModel):
    """Organisation info with user's role in that organisation."""
    org_id: str
    org_name: str
    org_slug: str
    role: str
    is_default: bool
    joined_at: datetime

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """Schema for login response.

    Returns user info and list of organisations they belong to.
    For org_admin/manager users, returns full tokens directly.
    For regular users, returns preliminary token for org selection.
    """
    success: bool = True
    user: UserResponse
    organisations: List[UserOrganisationInfo]
    requires_org_selection: bool = True
    preliminary_token: Optional[str] = Field(None, description="Temporary token for org selection (regular users)")
    # For org_admin/manager - direct login without org selection
    tokens: Optional[Token] = Field(None, description="Full tokens for org_admin/manager users")
    organisation: Optional[OrganisationBasic] = Field(None, description="Selected org for org_admin/manager users")
    role: Optional[str] = Field(None, description="User's role in the auto-selected organisation")


class SelectOrgResponse(BaseModel):
    """Schema for organisation selection response."""
    success: bool = True
    user: UserResponse
    organisation: OrganisationBasic
    role: str
    tokens: Token


class RegisterResponse(BaseModel):
    """Schema for registration response."""
    success: bool = True
    user: UserResponse
    message: str = "Registration successful. You can now join or create an organisation."


class RefreshTokenRequest(BaseModel):
    """Schema for token refresh request."""
    refresh_token: str


class LogoutRequest(BaseModel):
    """Schema for logout request."""
    refresh_token: Optional[str] = None
    logout_all_devices: bool = False
