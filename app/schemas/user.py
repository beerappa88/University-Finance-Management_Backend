"""
Pydantic schemas for users.

This module defines the request and response schemas for user-related
API endpoints using Pydantic models.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, validator
from uuid import UUID

class UserBase(BaseModel):
    """Base schema for user data."""
    
    username: str = Field(..., min_length=3, max_length=50, description="Username must be 3-50 characters")
    email: EmailStr = Field(..., description="Valid email address")
    full_name: str = Field(..., min_length=2, max_length=100, description="Full name must be 2-100 characters")
    role: str = Field("viewer", description="User role (admin, finance_manager, viewer)")
    is_active: bool = Field(True, description="Whether the user account is active")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    department: Optional[str] = Field(None, max_length=100, description="Department name")
    position: Optional[str] = Field(None, max_length=100, description="Job position")
    bio: Optional[str] = Field(None, max_length=500, description="User biography")
    profile_picture_url: Optional[str] = Field(None, description="URL to profile image")

class UserCreate(UserBase):
    """Schema for creating a new user."""
    
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    
    @validator('role')
    def validate_role(cls, v):
        allowed_roles = ['admin', 'finance_manager', 'viewer']
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of {allowed_roles}")
        return v

class UserUpdate(BaseModel):
    """Schema for updating a user."""
    
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    role: Optional[str] = None
    is_active: Optional[bool] = None
    phone: Optional[str] = Field(None, max_length=20)
    department: Optional[str] = Field(None, max_length=100)
    position: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    profile_picture_url: Optional[str] = None
    
    @validator('role')
    def validate_role(cls, v):
        if v is not None:
            allowed_roles = ['admin', 'finance_manager', 'viewer']
            if v not in allowed_roles:
                raise ValueError(f"Role must be one of {allowed_roles}")
        return v

class User(UserBase):
    """Schema for user response data."""
    
    id: UUID
    is_2fa_enabled: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    
    class Config:
        """Configuration for the User schema."""
        
        from_attribute = True
        
class UserInDB(User):
    """Schema for user data with password hash (for internal use)."""
    
    hashed_password: str
    totp_secret: Optional[str] = None
    backup_codes: Optional[List[str]] = None
    reset_token: Optional[str] = None
    reset_token_expires: Optional[datetime] = None

class Token(BaseModel):
    """Schema for authentication token."""
    
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """Schema for token data."""
    
    username: Optional[str] = None

class PasswordResetRequest(BaseModel):
    """Schema for password reset request."""
    
    email: EmailStr

class PasswordReset(BaseModel):
    """Schema for password reset."""
    
    token: str
    new_password: str

class ChangePassword(BaseModel):
    """Schema for changing password."""
    
    current_password: str
    new_password: str

class UserWithSensitiveInfo(User):
    """Schema for user response with sensitive information (admin only)."""
    
    reset_token: Optional[str] = None
    reset_token_expires: Optional[datetime] = None

class TwoFactorSetup(BaseModel):
    """Schema for TOTP setup."""
    
    secret: str
    uri: str
    backup_codes: List[str]

class TwoFactorVerify(BaseModel):
    """Schema for TOTP verification."""
    
    token: str = Field(..., min_length=6, max_length=6, description="6-digit TOTP code")

class BackupCodeVerify(BaseModel):
    """Schema for backup code verification."""
    
    code: str = Field(..., min_length=8, max_length=8, description="8-digit backup code")

class AccountDeletionRequest(BaseModel):
    """Schema for account deletion request."""
    
    password: str
    confirmation_text: str = Field(..., description="Must be 'DELETE MY ACCOUNT'")
