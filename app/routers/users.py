"""
User management endpoints.
This module provides endpoints for user management operations.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.deps import (
    can_read_user,
)
from app.core.rbac import (
    update_user_with_access, delete_user_with_access
)
from app.core.auth import get_current_user, get_current_active_user
from app.db.session import get_db
from app.schemas.user import User, UserUpdate
from app.models.user import User as UserModel
from app.services.user import UserService
from app.core.logging import logger
from uuid import UUID
router = APIRouter()

@router.get("/", response_model=List[User])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(can_read_user),
) -> List[UserModel]:
    """
    Get all users with pagination.
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of users
    """
    logger.info(f"User list requested by: {current_user.username}")
    
    result = await db.execute(select(UserModel).offset(skip).limit(limit))
    users = result.scalars().all()
    
    logger.info(f"Retrieved {len(users)} users")
    return users

@router.get("/{user_id}", response_model=User)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(can_read_user),
) -> UserModel:
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
) -> UserModel:
    """
    Update a user.
    
    Args:
        user_id: User ID
        user_in: User update data
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
