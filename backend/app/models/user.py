"""
User, UserSettings, and UserOrganisation Models

User authentication, preferences, and organisation membership for the Pedagogy application.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.core.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    """User model for authentication and authorization.

    Users exist independently of organisations and can belong to multiple
    organisations through the UserOrganisation junction table.
    """

    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)

    # Relationships
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    organisations = relationship("UserOrganisation", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(user_id={self.user_id}, email={self.email})>"


class UserOrganisation(Base):
    """Junction table for User-Organisation many-to-many relationship.

    Stores the user's role within each organisation they belong to.
    """

    __tablename__ = "user_organisations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    org_id = Column(String(36), ForeignKey("organisations.org_id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), default="user")  # org_admin, manager, user, viewer
    is_default = Column(Boolean, default=False)  # User's default organisation
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="organisations")
    organisation = relationship("Organisation", back_populates="members")

    def __repr__(self):
        return f"<UserOrganisation(user_id={self.user_id}, org_id={self.org_id}, role={self.role})>"


class UserSettings(Base):
    """User settings and preferences."""

    __tablename__ = "user_settings"

    setting_id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), unique=True, nullable=False)
    hotkey = Column(String(50), default="Ctrl+Shift+P")
    auto_capture_on_query = Column(Boolean, default=False)
    preferences = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="settings")

    def __repr__(self):
        return f"<UserSettings(user_id={self.user_id})>"
