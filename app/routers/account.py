"""
Account management endpoints.

This module provides endpoints for account management including account deletion.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.rbac import PermissionCache
from app.core.auth import get_current_active_user
from app.models.user import User as UserModel
from app.db.session import get_db
from app.core.security import verify_password
from app.core.logging import logger

router = APIRouter()


class AccountDeletionRequest(BaseModel):
    """Schema for account deletion request."""

    password: str
    confirmation_text: str = Field(..., description="Must be 'DELETE MY ACCOUNT'")


@router.delete("/account")
async def delete_account(
    deletion_request: AccountDeletionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> dict:
    """
    Delete user account.
    
    Args:
        deletion_request: Account deletion request data
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Status message
    """
    logger.info(f"Account deletion requested by user: {current_user.username}")
    
    # Verify password
    if not verify_password(deletion_request.password, current_user.hashed_password):
        logger.warning(f"Account deletion failed: Invalid password for user {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password"
        )
    
    # Verify confirmation text
    if deletion_request.confirmation_text != "DELETE MY ACCOUNT":
        logger.warning(f"Account deletion failed: Incorrect confirmation text for user {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation text is incorrect"
        )
    
    # Don't allow deleting the last admin
    if current_user.role == "admin":
        result = await db.execute(
            select(UserModel).where(UserModel.role == "admin", UserModel.is_active == True)
        )
        admin_count = len(result.scalars().all())
        
        if admin_count <= 1:
            logger.warning(f"Account deletion failed: Cannot delete last admin account ({current_user.username})")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last admin account"
            )
    
    # Delete user's sessions
    from app.models.session import UserSession
    await db.execute(
        delete(UserSession).where(UserSession.user_id == current_user.id)
    )
    
    # Delete user
    await db.delete(current_user)
    await db.commit()
    
    # Invalidate permission cache
    await PermissionCache.invalidate_user_permissions(current_user.id)
    
    logger.info(f"Account deleted successfully: {current_user.username}")
    return {"status": "success", "message": "Account deleted successfully"}
