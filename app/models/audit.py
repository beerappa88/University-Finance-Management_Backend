"""
Audit log model for tracking financial transactions and system changes.

This module defines the SQLAlchemy model for audit logs, which record
all important actions in the system for compliance and security.
"""

from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.models.base import Base


class AuditLog(Base):
    """
    Audit log model tracking system actions.
    
    Records all financial transactions and changes to sensitive data
    for compliance and security purposes.
    """
    
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(50), nullable=False)  # CREATE, UPDATE, etc.
    resource_type = Column(String(50), nullable=False)  # USER, BUDGET, etc.
    resource_id = Column(String(50), nullable=True)  # ID of the resource
    details = Column(JSON, nullable=True)  # Change details
    ip_address = Column(String(45), nullable=True)  # IPv4/IPv6
    user_agent = Column(String(255), nullable=True)  # Browser/device
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    user = relationship("User", back_populates="audit_logs", foreign_keys=[user_id])

    def __repr__(self):
        """String representation of the AuditLog model."""
        return (
            f"<AuditLog(id={self.id}, action='{self.action}', "
            f"resource_type='{self.resource_type}', user_id={self.user_id})>"
        )
