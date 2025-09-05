"""
ExportHistory model to track user export activities.

This module defines the SQLAlchemy model for export history,
which records user-initiated export activities.
"""

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, UUID
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
import uuid
from datetime import datetime

class ExportHistory(Base):
    __tablename__ = "export_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    export_type = Column(String, nullable=False)
    name = Column(String, nullable=False)
    params = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="completed")
    
    # Relationship to user
    user = relationship("User", back_populates="export_history")