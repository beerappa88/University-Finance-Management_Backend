"""
User model for authentication and authorization.
This module defines the SQLAlchemy model for users who can access the finance system.
"""
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base
from app.core.security import get_password_hash

class User(Base):
    """
    User model representing system users.
    
    Users can have different roles (admin, finance_manager, viewer)
    and are authenticated using JWT tokens.
    """
    
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    email = Column(String(100), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False, default="viewer")  # admin, finance_manager, viewer
    is_active = Column(Boolean, nullable=False, default=True)
    is_2fa_enabled = Column(Boolean, nullable=False, default=False)
    totp_secret = Column(String(255), nullable=True)
    backup_codes = Column(Text, nullable=True)  # JSON array of backup codes
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Department association - nullable to avoid circular dependency
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
        
    # Password reset fields
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)
    
    # Profile fields
    phone = Column(String(20), nullable=True)
    position = Column(String(100), nullable=True)
    bio = Column(Text, nullable=True)
    profile_picture_url = Column(String(255), nullable=True)
    
    # Relationships - using string references to avoid circular imports
    audit_logs = relationship(
        "AuditLog", 
        back_populates="user",
        cascade="all, delete-orphan"
    )
    reports = relationship(
        "Report", 
        back_populates="user",
        cascade="all, delete-orphan"
    )
    notification_preferences = relationship(
        "NotificationPreference", 
        back_populates="user",
        cascade="all, delete-orphan"
    )
    sessions = relationship(
        "UserSession", 
        back_populates="user",
        cascade="all, delete-orphan"
    )

    export_history = relationship("ExportHistory", back_populates="user")
    
    # Department relationship - explicitly specify foreign_keys
    department = relationship(
        "Department",
        back_populates="users",
        foreign_keys=[department_id]  # Explicitly specify which FK to use
    )
    
    # Managed departments (for department heads)
    managed_departments = relationship(
        "Department",
        foreign_keys="Department.head_user_id",
        back_populates="head_user"
    )
    
    def __repr__(self) -> str:
        """String representation of the User model."""
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"
    
    def set_password(self, password: str) -> None:
        """Set the user's password."""
        self.hashed_password = get_password_hash(password)
