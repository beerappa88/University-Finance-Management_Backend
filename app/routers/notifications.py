"""
Notification preferences endpoints.

This module provides endpoints for managing user notification preferences.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.deps import get_db
from app.core.auth import get_current_active_user
from app.models.user import User
from app.models.notification import NotificationPreference 
from app.schemas.notification import (
    NotificationPreference as NotificationPreferenceSchema,
    NotificationPreferenceUpdate,
)

router = APIRouter()


@router.get("/notification-preferences", response_model=NotificationPreferenceSchema)
async def get_notification_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get user's notification preferences.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        User's notification preferences
    """
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == current_user.id
        )
    )
    preferences = result.scalars().first()
    
    if not preferences:
        # Create default preferences if they don't exist
        preferences = NotificationPreference(user_id=current_user.id)
        db.add(preferences)
        await db.commit()
        await db.refresh(preferences)
    
    return preferences


@router.put("/notification-preferences", response_model=NotificationPreferenceSchema)
async def update_notification_preferences(
    preferences_data: NotificationPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Update user's notification preferences.
    
    Args:
        preferences_data: Notification preference update data
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Updated notification preferences
    """
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == current_user.id
        )
    )
    preferences = result.scalars().first()
    
    if not preferences:
        # Create preferences if they don't exist
        preferences = NotificationPreference(
            user_id=current_user.id,
            **preferences_data.dict(exclude_unset=True)
        )
        db.add(preferences)
    else:
        # Update existing preferences
        for field, value in preferences_data.dict(exclude_unset=True).items():
            setattr(preferences, field, value)
    
    await db.commit()
    await db.refresh(preferences)
    
    return preferences