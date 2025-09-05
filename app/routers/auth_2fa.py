"""
Two-factor authentication endpoints.

This module provides endpoints for enabling, disabling, and verifying two-factor authentication.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.core.security import (
    generate_totp_secret, 
    generate_totp_uri, 
    verify_totp,
    generate_backup_codes,
    verify_backup_code
)
from app.db.session import get_db
from app.core.auth import get_current_active_user
from app.models.user import User as UserModel
from app.core.rbac import PermissionCache
from app.core.logging import logger
import json

router = APIRouter()


class TOTPSetup(BaseModel):
    """TOTP setup schema."""

    secret: str
    uri: str
    backup_codes: list[str]


class TOTPVerify(BaseModel):
    """TOTP verification schema."""

    token: str = Field(..., min_length=6, max_length=6)


class BackupCodeVerify(BaseModel):
    """Backup code verification schema."""

    code: str = Field(..., min_length=8, max_length=8)


@router.post("/enable-2fa", response_model=TOTPSetup)
async def enable_2fa(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> Any:
    """
    Enable two-factor authentication for the current user.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        TOTP setup information including secret and QR code URI
    """
    logger.info(f"2FA enable attempt by user: {current_user.username}")
    
    if current_user.is_2fa_enabled:
        logger.warning(f"2FA already enabled for user: {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is already enabled"
        )
    
    # Generate TOTP secret
    totp_secret = generate_totp_secret()
    
    # Generate backup codes
    backup_codes = generate_backup_codes()
    
    # Generate QR code URI
    totp_uri = generate_totp_uri(totp_secret, current_user.username)
    
    # Update user with 2FA settings
    current_user.totp_secret = totp_secret
    current_user.backup_codes = json.dumps(backup_codes)
    
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    
    # Invalidate permission cache when 2FA status changes
    await PermissionCache.invalidate_user_permissions(current_user.id)
    
    return {
        "secret": totp_secret,
        "uri": totp_uri,
        "backup_codes": backup_codes
    }


@router.post("/verify-2fa")
async def verify_2fa(
    verification_data: TOTPVerify,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> dict:
    """
    Verify two-factor authentication code.
    
    Args:
        verification_data: TOTP verification data
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Verification result
    """
    logger.info(f"2FA verification attempt by user: {current_user.username}")
    
    if not current_user.totp_secret:
        logger.warning(f"2FA not enabled for user: {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is not enabled"
        )
    
    # Verify TOTP token
    if verify_totp(current_user.totp_secret, verification_data.token):
        # Enable 2FA
        current_user.is_2fa_enabled = True
        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)
        
        # Invalidate permission cache when 2FA status changes
        await PermissionCache.invalidate_user_permissions(current_user.id)
        
        logger.info(f"2FA enabled successfully for user: {current_user.username}")
        return {"status": "success", "message": "Two-factor authentication enabled"}
    
    # Check backup codes if TOTP fails
    if current_user.backup_codes and verify_backup_code(
        current_user.backup_codes, 
        verification_data.token
    ):
        # Update backup codes (remove used code)
        current_user.backup_codes = json.dumps(
            json.loads(current_user.backup_codes).filter(lambda x: x != verification_data.token)
        )
        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)
        
        logger.info(f"2FA enabled with backup code for user: {current_user.username}")
        return {"status": "success", "message": "Backup code used"}
    
    logger.warning(f"2FA verification failed for user: {current_user.username}")
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid verification code"
    )


@router.post("/disable-2fa")
async def disable_2fa(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> dict:
    """
    Disable two-factor authentication for the current user.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Status message
    """
    logger.info(f"2FA disable attempt by user: {current_user.username}")
    
    if not current_user.is_2fa_enabled:
        logger.warning(f"2FA not enabled for user: {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is not enabled"
        )
    
    # Disable 2FA
    current_user.is_2fa_enabled = False
    current_user.totp_secret = None
    current_user.backup_codes = None
    
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    
    # Invalidate permission cache when 2FA status changes
    await PermissionCache.invalidate_user_permissions(current_user.id)
    
    logger.info(f"2FA disabled successfully for user: {current_user.username}")
    return {"status": "success", "message": "Two-factor authentication disabled"}