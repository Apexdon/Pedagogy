"""
Guidance Session Models

Database models for AI Guidance Engine sessions, steps, and captures.
"""

from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey, JSON, Float, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from app.core.database import Base


class SessionStatus(str, enum.Enum):
    """Guidance session status."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    ERROR = "error"


class StepStatus(str, enum.Enum):
    """Guidance step status."""
    PENDING = "pending"
    CURRENT = "current"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class ActionType(str, enum.Enum):
    """UI action types for guidance steps."""
    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    SCROLL = "scroll"
    HOVER = "hover"
    WAIT = "wait"
    VERIFY = "verify"
    NAVIGATE = "navigate"


class GuidanceSession(Base):
    """
    Guidance session model.

    Tracks a user's guidance session from query to completion.
    """
    __tablename__ = "guidance_sessions"

    session_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    org_id = Column(String(36), ForeignKey("organisations.org_id"), nullable=False)

    # Query and context
    query = Column(Text, nullable=False)
    application_context = Column(String(255), nullable=True)  # e.g., "GitHub - Issues"

    # Session state
    status = Column(String(20), default=SessionStatus.ACTIVE.value)
    current_step = Column(Integer, default=0)
    total_steps = Column(Integer, default=0)

    # RAG context
    kb_id = Column(String(36), ForeignKey("knowledge_bases.kb_id"), nullable=True)
    rag_context = Column(JSON, nullable=True)  # Stored RAG results for the session

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    # Relationships - Note: order_by removed to avoid async issues, sort manually after loading
    steps = relationship("GuidanceStep", back_populates="session", cascade="all, delete-orphan")
    captures = relationship("GuidanceCapture", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<GuidanceSession(session_id={self.session_id}, query='{self.query[:50]}...', status={self.status})>"


class GuidanceStep(Base):
    """
    Guidance step model.

    Represents a single step in a guidance sequence.
    """
    __tablename__ = "guidance_steps"

    step_id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("guidance_sessions.session_id"), nullable=False)

    # Step info
    step_number = Column(Integer, nullable=False)
    instruction = Column(Text, nullable=False)  # Human-readable instruction
    detailed_instruction = Column(Text, nullable=True)  # More detailed explanation

    # Target element info (for Halo highlighting)
    target_element_type = Column(String(50), nullable=True)  # e.g., "button", "input", "link"
    target_element_label = Column(String(255), nullable=True)  # e.g., "Submit", "Search..."
    target_selector = Column(String(255), nullable=True)  # CSS selector if available
    target_bbox = Column(JSON, nullable=True)  # Bounding box: {x1, y1, x2, y2}

    # Action info
    action_type = Column(String(20), default=ActionType.CLICK.value)
    action_value = Column(Text, nullable=True)  # Value for type/select actions

    # Matching confidence
    match_confidence = Column(Float, nullable=True)  # 0.0 - 1.0

    # Step state
    status = Column(String(20), default=StepStatus.PENDING.value)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    session = relationship("GuidanceSession", back_populates="steps")

    def __repr__(self):
        return f"<GuidanceStep(step_id={self.step_id}, step_number={self.step_number}, instruction='{self.instruction[:30]}...')>"


class GuidanceCapture(Base):
    """
    Guidance capture model.

    Stores screen captures taken during guidance sessions.
    """
    __tablename__ = "guidance_captures"

    capture_id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("guidance_sessions.session_id"), nullable=False)
    step_id = Column(String(36), ForeignKey("guidance_steps.step_id"), nullable=True)

    # Capture info
    capture_type = Column(String(20), default="step")  # "initial", "step", "verification"
    screenshot_path = Column(String(512), nullable=True)
    screenshot_base64 = Column(Text, nullable=True)  # For quick access

    # Detection results
    screen_state = Column(JSON, nullable=True)  # Full ScreenState from CV pipeline
    element_count = Column(Integer, default=0)
    text_region_count = Column(Integer, default=0)

    # Processing info
    processing_time_ms = Column(Float, nullable=True)

    # Timestamps
    captured_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    session = relationship("GuidanceSession", back_populates="captures")

    def __repr__(self):
        return f"<GuidanceCapture(capture_id={self.capture_id}, type={self.capture_type})>"
