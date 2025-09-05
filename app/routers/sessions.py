"""
Session management endpoints.
This module provides endpoints for managing user sessions and login activity.
"""
from typing import Any, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from app.core.security import create_access_token
from app.db.session import get_db
from app.core.auth import get_current_active_user   
from app.models.user import User as UserModel
from app.models.session import UserSession
from app.schemas.session import Session, LoginActivity
from app.utils.pagination import PaginationParams, PaginatedResponse, paginate_query
from app.core.deps import get_pagination_params
from uuid import UUID
from app.core.logging import logger

router = APIRouter()

@router.get("/login-activity", response_model=PaginatedResponse[LoginActivity])
async def get_login_activity(
    request: Request,
    db: AsyncSession = Depends(get_db),
    pagination: PaginationParams = Depends(get_pagination_params),
    current_user: UserModel = Depends(get_current_active_user)
) -> PaginatedResponse[LoginActivity]:
    """
    Get user's login activity history with pagination.
    
    Args:
        request: The request object
        db: Database session
        pagination: Pagination parameters
        current_user: Current authenticated user
        
    Returns:
        Paginated list of login activity records
    """
    # Base query filtered by current user
    stmt = select(UserSession).where(
        UserSession.user_id == current_user.id
    ).order_by(UserSession.created_at.desc())
    
    # Create count query for performance
    count_query = select(func.count(UserSession.id)).where(
        UserSession.user_id == current_user.id
    )
    
    # Execute paginated query
    result = await paginate_query(db, stmt, pagination, count_query, UserSession)
    
    # Get current session token
    current_token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        current_token = auth_header.split(" ")[1]
    
    # Transform items to response format
    transformed_items = []
    for item in result.items:
        transformed_items.append(LoginActivity(
            id=item.id,
            username=current_user.username,
            ip_address=item.ip_address,
            user_agent=item.user_agent,
            login_time=item.created_at,
            last_activity=item.last_activity,
            is_current=item.session_token == current_token
        ))
    
    # Create a new PaginatedResponse with the transformed items
    transformed_result = PaginatedResponse(
        items=transformed_items,
        total=result.total,
        page=result.page,
        size=result.size,
        pages=result.pages,
        has_next=result.has_next,
        has_prev=result.has_prev
    )
    
    logger.info(f"Retrieved {len(transformed_items)} login activity records (page {transformed_result.page} of {transformed_result.pages})")
    
    return transformed_result

@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: UUID,
    request: Request,
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
    auth_header = request.headers.get("Authorization")
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
    request: Request,
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
    auth_header = request.headers.get("Authorization")
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
    request: Request
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
