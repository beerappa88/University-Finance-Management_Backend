"""
Session management endpoints.

This module provides endpoints for managing user sessions and login activity.
"""

from typing import Any, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.core.security import create_access_token
from app.db.session import get_db
from app.core.auth import get_current_active_user   
from app.models.user import User as UserModel
from app.models.session import UserSession
from app.schemas.session import Session, LoginActivity
from uuid import UUID

router = APIRouter()

@router.get("/login-activity", response_model=List[LoginActivity])
async def get_login_activity(
    request: Request,  # Add request parameter
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> Any:
    """
    Get user's login activity history.
    
    Args:
        request: The request object
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of login activity records
    """
    result = await db.execute(
        select(UserSession).where(
            UserSession.user_id == current_user.id
        ).order_by(UserSession.created_at.desc())
    )
    sessions = result.scalars().all()
    
    # Get current session token
    current_token = None
    auth_header = request.headers.get("Authorization")  # Use request instance instead of Request class
    if auth_header and auth_header.startswith("Bearer "):
        current_token = auth_header.split(" ")[1]
    
    activity = []
    for session in sessions:
        activity.append({
            "id": session.id,
            "username": current_user.username,
            "ip_address": session.ip_address,
            "user_agent": session.user_agent,
            "login_time": session.created_at,
            "last_activity": session.last_activity,
            "is_current": session.session_token == current_token
        })
    
    return activity

@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: UUID,
    request: Request,  # Add request parameter
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> dict:
    """
    Revoke a specific session.
    
    Args:
        session_id: Session ID to revoke
        request: The request object
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Status message
    """
    result = await db.execute(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == current_user.id
        )
    )
    session = result.scalars().first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Don't allow revoking current session
    current_token = None
    auth_header = request.headers.get("Authorization")  # Use request instance instead of Request class
    if auth_header and auth_header.startswith("Bearer "):
        current_token = auth_header.split(" ")[1]
    
    if session.session_token == current_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot revoke current session"
        )
    
    await db.delete(session)
    await db.commit()
    
    return {"status": "success", "message": "Session revoked"}

@router.delete("/sessions")
async def revoke_all_sessions(
    request: Request,  # Add request parameter
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> dict:
    """
    Revoke all sessions except current session.
    
    Args:
        request: The request object
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Status message
    """
    # Get current session token
    current_token = None
    auth_header = request.headers.get("Authorization")  # Use request instance instead of Request class
    if auth_header and auth_header.startswith("Bearer "):
        current_token = auth_header.split(" ")[1]
    
    # Delete all sessions except current
    await db.execute(
        delete(UserSession).where(
            UserSession.user_id == current_user.id,
            UserSession.session_token != current_token
        )
    )
    await db.commit()
    
    return {"status": "success", "message": "All sessions revoked except current"}

# Helper function to create session (to be called from login endpoint)
async def create_user_session(
    db: AsyncSession, 
    user: UserModel, 
    token: str, 
    request: Request  # Add request parameter
) -> UserSession:
    """
    Create a new user session.
    
    Args:
        db: Database session
        user: User object
        token: JWT token
        request: Request object
        
    Returns:
        Created session
    """
    # Get client IP address
    ip_address = request.client.host
    
    # Get user agent
    user_agent = request.headers.get("user-agent", "")
    
    # Set expiration time (30 days from now)
    expires_at = datetime.utcnow() + timedelta(days=30)
    
    # Create session
    session = UserSession(
        user_id=user.id,
        session_token=token,
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=expires_at
    )
    
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    return session