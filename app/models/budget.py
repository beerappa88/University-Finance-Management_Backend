"""
Budget model for the university finance system.

This module defines the SQLAlchemy model for budgets,
which represent the allocated funds for departments.
"""

from decimal import Decimal
from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

class Budget(Base):
    """
    Budget model representing the allocated funds for a department.
    
    Budgets track the allocated amount, spent amount, and remaining balance
    for a department in a specific fiscal year.
    """
    
    __tablename__ = "budgets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False)
    fiscal_year = Column(String(10), nullable=False)  # e.g., "2023-2024"
    total_amount = Column(Numeric(15, 2), nullable=False)
    spent_amount = Column(Numeric(15, 2), nullable=False, default=Decimal("0.00"))
    remaining_amount = Column(Numeric(15, 2), nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships - use lazy loading to avoid async issues
    department = relationship("Department", back_populates="budgets", lazy="selectin")
    transactions = relationship("Transaction", back_populates="budget", lazy="selectin", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        """String representation of the Budget model."""
        # Only use attributes that are always available
        return (
            f"<Budget(id={self.id}, "
            f"department_id={self.department_id}, "
            f"fiscal_year='{self.fiscal_year}', "
            f"total_amount={self.total_amount})>"
        )
