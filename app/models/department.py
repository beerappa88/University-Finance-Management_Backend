"""
Department model for the university finance system.
This module defines the SQLAlchemy model for departments,
which are fundamental units in the university's financial structure.
"""
from sqlalchemy import Column, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

class Department(Base):
    """
    Department model representing a university department.
    
    Departments are the basic organizational units that have budgets
    and financial transactions. Enhanced with RBAC support.
    """
    
    __tablename__ = "departments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True, index=True)
    code = Column(String(20), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    
    # RBAC and organizational fields
    head_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Timestamp fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships - using string references to avoid circular imports
    budgets = relationship(
        "Budget", 
        back_populates="department",
        cascade="all, delete-orphan",
        order_by="Budget.fiscal_year.desc()"
    )
    
    # Head of department relationship
    head_user = relationship(
        "User",
        foreign_keys=[head_user_id],
        back_populates="managed_departments"
    )
    
    # Users in this department - explicitly specify foreign_keys to resolve ambiguity
    users = relationship(
        "User",
        back_populates="department",
        cascade="all, delete-orphan",
        foreign_keys="[User.department_id]"  # Specify which foreign key to use
    )
    
    def __repr__(self) -> str:
        """String representation of the Department model."""
        return f"<Department(id={self.id}, name='{self.name}', code='{self.code}')>"
