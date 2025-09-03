"""
Pydantic schemas for notification preferences.

This module defines the request and response schemas for notification-related
API endpoints using Pydantic models.
"""

from typing import Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NotificationPreferenceBase(BaseModel):
    """Base schema for notification preference data."""
    
    email_notifications: bool = True
    sms_notifications: bool = False
    push_notifications: bool = False
    login_alerts: bool = True
    transaction_alerts: bool = True
    budget_alerts: bool = True
    system_updates: bool = True


class NotificationPreferenceCreate(NotificationPreferenceBase):
    """Schema for creating notification preferences."""
    
    pass


class NotificationPreferenceUpdate(BaseModel):
    """Schema for updating notification preferences."""
    
    email_notifications: Optional[bool] = None
    sms_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    login_alerts: Optional[bool] = None
    transaction_alerts: Optional[bool] = None
    budget_alerts: Optional[bool] = None
    system_updates: Optional[bool] = None


class NotificationPreference(NotificationPreferenceBase):
    """Schema for notification preference response data."""
    
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        """Configuration for the NotificationPreference schema."""
        
        from_attributes = True