"""
Notification model for user notification preferences.

This module defines the SQLAlchemy model for user notification preferences.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.models.base import Base
from app.models.user import User


class NotificationPreference(Base):
    """
    Notification preference model for users.
    
    Stores user preferences for different types of notifications.
    """
    
    __tablename__ = "notification_preferences"
    
    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    email_notifications = Column(Boolean, nullable=False, default=True)
    sms_notifications = Column(Boolean, nullable=False, default=False)
    push_notifications = Column(Boolean, nullable=False, default=False)
    login_alerts = Column(Boolean, nullable=False, default=True)
    transaction_alerts = Column(Boolean, nullable=False, default=True)
    budget_alerts = Column(Boolean, nullable=False, default=True)
    system_updates = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship
    user = relationship("User", back_populates="notification_preferences")
    
    def __repr__(self) -> str:
        """String representation of the NotificationPreference model."""
        return f"<NotificationPreference(id={self.id}, user_id={self.user_id})>"
