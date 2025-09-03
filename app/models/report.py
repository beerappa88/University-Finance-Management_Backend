"""
Report model for storing generated financial reports.

This module defines the SQLAlchemy model for financial reports,
which can be generated on-demand or scheduled.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class Report(Base):
    """
    Report model for financial reports.
    
    Stores generated reports with their parameters and results.
    """
    
    __tablename__ = "reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    report_type = Column(String(50), nullable=False)  # BUDGET_VS_ACTUAL, DEPARTMENT_SPENDING, etc.
    parameters = Column(JSON, nullable=False)  # Report parameters
    results = Column(JSON, nullable=True)  # Report results
    generated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="reports")
    
    def __repr__(self) -> str:
        """String representation of the Report model."""
        return (
            f"<Report(id={self.id}, name='{self.name}', "
            f"type='{self.report_type}', generated_by={self.generated_by})>"
        )
