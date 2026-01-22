"""
Target Application Schemas

Pydantic models for target application requests and responses.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


# Match mode type
MatchMode = Literal["url", "process", "title", "auto"]


# ============================================
# Create/Update Schemas
# ============================================

class TargetAppCreate(BaseModel):
    """Schema for creating a target application."""

    app_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

    # Matching configuration
    match_mode: MatchMode = "auto"
    url_pattern: Optional[str] = Field(None, max_length=500)
    url_patterns: Optional[List[str]] = None
    brand_keywords: Optional[List[str]] = None  # Keywords for visual verification via OCR
    process_name: Optional[str] = Field(None, max_length=255)
    window_pattern: Optional[str] = Field(None, max_length=500)
    window_class: Optional[str] = Field(None, max_length=255)
    app_config: Optional[Dict[str, Any]] = None

    is_active: bool = True
    is_default: bool = False


class TargetAppUpdate(BaseModel):
    """Schema for updating a target application."""

    app_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None

    # Matching configuration
    match_mode: Optional[MatchMode] = None
    url_pattern: Optional[str] = Field(None, max_length=500)
    url_patterns: Optional[List[str]] = None
    brand_keywords: Optional[List[str]] = None  # Keywords for visual verification via OCR
    process_name: Optional[str] = Field(None, max_length=255)
    window_pattern: Optional[str] = Field(None, max_length=500)
    window_class: Optional[str] = Field(None, max_length=255)
    app_config: Optional[Dict[str, Any]] = None

    is_active: Optional[bool] = None


# ============================================
# Response Schemas
# ============================================

class TargetAppResponse(BaseModel):
    """Schema for target application response."""

    app_id: str
    org_id: str
    app_name: str
    description: Optional[str] = None

    # Matching configuration
    match_mode: str
    url_pattern: Optional[str] = None
    url_patterns: Optional[List[str]] = None
    brand_keywords: Optional[List[str]] = None  # Keywords for visual verification via OCR
    process_name: Optional[str] = None
    window_pattern: Optional[str] = None
    window_class: Optional[str] = None
    app_config: Optional[Dict[str, Any]] = None

    # Status
    is_active: bool
    is_default: bool
    is_configured: bool  # Computed property

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TargetAppListResponse(BaseModel):
    """Schema for list of target applications."""

    target_apps: List[TargetAppResponse]
    total_count: int


class TargetAppDeleteResponse(BaseModel):
    """Schema for delete target app response."""

    success: bool = True
    message: str
    app_id: str


class SetDefaultResponse(BaseModel):
    """Schema for set default response."""

    success: bool = True
    message: str
    app_id: str
    previous_default_id: Optional[str] = None


# ============================================
# Settings Schema (for backwards compatibility)
# ============================================

class TargetAppSettingsResponse(BaseModel):
    """Schema matching the old target app settings format.

    Used for backwards compatibility with existing endpoints.
    """

    org_id: str
    target_app_name: Optional[str] = None
    target_window_pattern: Optional[str] = None
    target_process_name: Optional[str] = None
    target_window_class: Optional[str] = None
    target_app_config: Optional[Dict[str, Any]] = None
    target_match_mode: str = "auto"
    target_url_pattern: Optional[str] = None
    target_url_patterns: Optional[List[str]] = None
    target_brand_keywords: Optional[List[str]] = None  # Keywords for visual verification
    is_configured: bool = False

    # New field to indicate this came from the new model
    app_id: Optional[str] = None

    @classmethod
    def from_target_app(cls, org_id: str, target_app: Optional["TargetAppResponse"]) -> "TargetAppSettingsResponse":
        """Convert a TargetAppResponse to the legacy settings format."""
        if target_app is None:
            return cls(
                org_id=org_id,
                is_configured=False
            )

        return cls(
            org_id=org_id,
            target_app_name=target_app.app_name,
            target_window_pattern=target_app.window_pattern,
            target_process_name=target_app.process_name,
            target_window_class=target_app.window_class,
            target_app_config=target_app.app_config,
            target_match_mode=target_app.match_mode,
            target_url_pattern=target_app.url_pattern,
            target_url_patterns=target_app.url_patterns,
            target_brand_keywords=target_app.brand_keywords,
            is_configured=target_app.is_configured,
            app_id=target_app.app_id
        )
