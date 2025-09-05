"""
User management endpoints.
This module provides endpoints for user management operations.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.core.deps import (
    can_read_user,
)
from app.core.deps import get_pagination_params
from app.core.rbac import (
    update_user_with_access, delete_user_with_access
)
from app.core.auth import get_current_user, get_current_active_user
from app.db.session import get_db
from app.schemas.user import User, UserUpdate
from app.models.user import User as UserModel
from app.services.user import UserService
from app.core.logging import logger
from app.utils.pagination import PaginationParams, PaginatedResponse, paginate_query
from uuid import UUID

router = APIRouter()

@router.get("/", response_model=PaginatedResponse[User])
async def get_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
    pagination: PaginationParams = Depends(get_pagination_params),
    search: Optional[str] = Query(None, description="Search by username or email"),
    role: Optional[str] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: UserModel = Depends(can_read_user),
) -> PaginatedResponse[User]:
    """
    Get all users with pagination, search, and filtering.
    
    Args:
        request: Request object
        db: Database session
        pagination: Pagination parameters
        search: Search term for username or email
        role: Filter by role
        is_active: Filter by active status
        current_user: Current authenticated user
        
    Returns:
        Paginated list of users
    """
    logger.info(f"User list requested by: {current_user.username}")
    
    # Base query
    stmt = select(UserModel)
    
    # Apply filters
    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(
            or_(
                UserModel.username.ilike(search_term),
                UserModel.email.ilike(search_term),
                UserModel.full_name.ilike(search_term)
            )
        )
    
    if role:
        stmt = stmt.where(UserModel.role == role)
    
    if is_active is not None:
        stmt = stmt.where(UserModel.is_active == is_active)
    
    # Create count query for performance
    count_query = select(func.count(UserModel.id))
    if search:
        search_term = f"%{search}%"
        count_query = count_query.where(
            or_(
                UserModel.username.ilike(search_term),
                UserModel.email.ilike(search_term),
                UserModel.full_name.ilike(search_term)
            )
        )
    
    if role:
        count_query = count_query.where(UserModel.role == role)
    
    if is_active is not None:
        count_query = count_query.where(UserModel.is_active == is_active)
    
    # Execute paginated query
    result = await paginate_query(db, stmt, pagination, count_query, UserModel)
    
    logger.info(f"Retrieved {len(result.items)} users (page {result.page} of {result.pages})")
    
    return result

@router.get("/{user_id}", response_model=User)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(can_read_user),
) -> User:
    """
    Get a user by ID.
    
    Args:
        user_id: User ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        User if found
        
    Raises:
        HTTPException: If user not found
    """
    logger.info(f"User details requested for ID: {user_id} by: {current_user.username}")
    
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalars().first()
    
    if not user:
        logger.warning(f"User not found: {user_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    return user

@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: UUID,
    user_in: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(update_user_with_access),
) -> User:
    """
    Update a user.
    
    Args:
        user_id: User ID
        user_in: User update data
        request: Request object
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Updated user
        
    Raises:
        HTTPException: If user not found
    """
    logger.info(f"User update requested for ID: {user_id} by: {current_user.username}")
    
    updated_user = await UserService.update(
        db=db,
        user_id=user_id,
        user_in=user_in,
        request=request,
        acting_user_id=current_user.id 
    )
    
    if not updated_user:
        logger.error(f"User not found for update: {user_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    logger.info(f"User updated successfully: {user_id}")
    return updated_user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(delete_user_with_access),
) -> None:
    """
    Delete a user.
    
    Args:
        user_id: User ID
        request: Request object
        db: Database session
        current_user: Current authenticated user
        
    Raises:
        HTTPException: If user not found or deletion fails
    """
    logger.info(f"User deletion requested for ID: {user_id} by: {current_user.username}")
    
    success = await UserService.delete(
        db=db,
        user_id=user_id,
        request=request,
        acting_user_id=current_user.id  
    )
    
    if not success:
        logger.error(f"User not found for deletion: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    logger.info(f"User deleted successfully: {user_id}")
    return None
