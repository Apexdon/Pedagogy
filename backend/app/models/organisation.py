"""
Organisation Model

Represents an organisation that users can belong to.
Users can be members of multiple organisations.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.core.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class Organisation(Base):
    """Organisation model - users can belong to multiple organisations."""

    __tablename__ = "organisations"

    org_id = Column(String(36), primary_key=True, default=generate_uuid)
    org_name = Column(String(255), nullable=False)
    org_slug = Column(String(100), unique=True, nullable=False)
    logo_path = Column(String(500), nullable=True)
    primary_color = Column(String(7), default="#3B82F6")
    subscription_tier = Column(String(50), default="standard")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Target Application Settings (for CV pipeline window capture)
    target_app_name = Column(String(255), nullable=True)  # e.g., "VS Code", "Salesforce"
    target_window_pattern = Column(String(500), nullable=True)  # e.g., "*Visual Studio Code*" (legacy)
    target_process_name = Column(String(255), nullable=True)  # e.g., "Code.exe", "chrome.exe"
    target_window_class = Column(String(255), nullable=True)  # Windows-specific class name
    target_app_config = Column(JSON, nullable=True)  # Additional app-specific config

    # Smart Target Matching (Phase 8 - improved window detection)
    target_match_mode = Column(String(50), default="auto")  # "url" | "process" | "title" | "auto"
    target_url_pattern = Column(String(500), nullable=True)  # For websites: "rs-online.com" or "*.salesforce.com"
    target_url_patterns = Column(JSON, nullable=True)  # Array of URL patterns for multi-domain sites

    # Relationships - through junction table
    members = relationship("UserOrganisation", back_populates="organisation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Organisation(org_id={self.org_id}, name={self.org_name})>"

    @property
    def has_target_app_configured(self) -> bool:
        """Check if target application is configured for this org."""
        return bool(self.target_window_pattern or self.target_process_name)
