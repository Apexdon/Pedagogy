"""
Target Application Model

Represents a target application that an organisation can track.
Each organisation can have multiple target applications (websites, desktop apps, etc.)
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.core.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class TargetApplication(Base):
    """Target Application model - applications/websites an organisation wants to guide users through.

    Supports multiple matching strategies:
    - URL: Match browser URL against patterns (best for websites)
    - Process: Match process name (best for desktop apps)
    - Title: Match window title (legacy fallback)
    - Auto: Try all strategies in order (URL -> Process -> Title)
    """

    __tablename__ = "target_applications"

    app_id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(
        String(36),
        ForeignKey("organisations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Basic info
    app_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Matching configuration
    match_mode = Column(String(50), default="auto")  # "url" | "process" | "title" | "auto"
    url_pattern = Column(String(500), nullable=True)  # Primary URL pattern (e.g., "rs-online.com")
    url_patterns = Column(JSON, nullable=True)  # Array of URL patterns for multi-domain sites
    brand_keywords = Column(JSON, nullable=True)  # Keywords to verify visually via OCR (e.g., ["RS Components", "rs-online"])
    process_name = Column(String(255), nullable=True)  # e.g., "Code.exe", "chrome.exe"
    window_pattern = Column(String(500), nullable=True)  # Legacy window title pattern (e.g., "*Visual Studio Code*")
    window_class = Column(String(255), nullable=True)  # Windows-specific class name
    app_config = Column(JSON, nullable=True)  # Additional app-specific config

    # Status
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # Only one per org should be default

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    organisation = relationship("Organisation", backref="target_applications")

    def __repr__(self):
        return f"<TargetApplication(app_id={self.app_id}, name={self.app_name}, mode={self.match_mode})>"

    @property
    def is_configured(self) -> bool:
        """Check if the target application has at least one matching pattern configured."""
        return bool(
            self.url_pattern or
            self.url_patterns or
            self.brand_keywords or
            self.process_name or
            self.window_pattern
        )

    @property
    def effective_brand_keywords(self) -> list[str]:
        """Get brand keywords as a list."""
        if self.brand_keywords and isinstance(self.brand_keywords, list):
            return self.brand_keywords
        return []

    @property
    def effective_url_patterns(self) -> list[str]:
        """Get all URL patterns as a list."""
        patterns = []
        if self.url_pattern:
            patterns.append(self.url_pattern)
        if self.url_patterns:
            patterns.extend(self.url_patterns)
        return patterns
