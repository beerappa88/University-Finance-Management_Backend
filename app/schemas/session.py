"""
Pydantic schemas for user sessions.

This module defines the request and response schemas for session-related
API endpoints using Pydantic models.
"""

from typing import Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SessionBase(BaseModel):
    """Base schema for session data."""
    
    session_token: str
    ip_address: str
    user_agent: Optional[str] = None
    is_active: bool = True
    expires_at: datetime


class SessionCreate(SessionBase):
    """Schema for creating a session."""
    
    user_id: UUID


class Session(SessionBase):
    """Schema for session response data."""
    
    id: UUID
    user_id: UUID
    created_at: datetime
    last_activity: datetime
    
    class Config:
        """Configuration for the Session schema."""
        
        orm_mode = True


class LoginActivity(BaseModel):
    """Schema for login activity."""
    
    id: UUID
    username: str
    ip_address: str
    user_agent: str
    login_time: datetime
    last_activity: datetime
    is_current: bool