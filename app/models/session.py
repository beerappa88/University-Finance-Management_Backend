"""
Session model for user sessions.

This module defines the SQLAlchemy model for user sessions.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.models.base import Base

class UserSession(Base):
    """
    User session model for tracking user sessions.
    
    Stores information about user login sessions for security monitoring.
    """
    
    __tablename__ = "user_sessions"
    
    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    session_token = Column(String(255), nullable=False, unique=True)
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Relationship
    user = relationship("User", back_populates="sessions")
    
    def __repr__(self) -> str:
        """String representation of the UserSession model."""
        return f"<UserSession(id={self.id}, user_id={self.user_id}, token={self.session_token[:10]}...)"
