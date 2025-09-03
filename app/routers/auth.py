"""
Authentication endpoints.
This module provides endpoints for user registration, 
login, and password reset.
"""
from datetime import datetime, timedelta
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4, UUID
from fastapi import UploadFile, File, Form
from pathlib import Path
from app.core.config import settings
from app.core.security import create_access_token, verify_password, get_password_hash
from app.db.session import get_db
from app.core.email import EmailService
from app.schemas.user import Token, UserCreate, User as UserSchema, PasswordResetRequest, PasswordReset, UserUpdate
from app.models.user import User as UserModel
from app.services.user import UserService
from app.core.rbac import PermissionCache
from app.core.auth import get_current_active_user
from app.db.audit import log_action_async  
import secrets
from app.routers.sessions import create_user_session
from app.core.logging import logger
from app.core.security import TokenManager
from app.core.cache import set_cache, get_cache, delete_cache

router = APIRouter()

@router.post("/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Register a new user.
    
    Args:
        user_in: User creation data
        request: FastAPI request (for IP and User-Agent)
        db: Database session
        
    Returns:
        Created user
        
    Raises:
        HTTPException: If user already exists
    """
    # Check if user already exists
    logger.info(f"Registration attempt for username: {user_in.username}")
    
    # Check if user already exists
    result = await db.execute(
        select(UserModel).where(UserModel.username == user_in.username)
    )
    if result.scalars().first():
        logger.warning(f"Registration failed: Username already exists - {user_in.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email already exists
    result = await db.execute(
        select(UserModel).where(UserModel.email == user_in.email)
    )
    if result.scalars().first():
        logger.warning(f"Registration failed: Email already exists - {user_in.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user with audit
    user = await UserService.create(
        db=db,
        user_in=user_in,
        request=request,
        acting_user_id=None 
    )
    
    logger.info(f"User registered successfully: {user.username}")
    return user

# Update the login endpoint to issue both access and refresh tokens
@router.post("/token", response_model=Token)
async def login_for_access_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """
    Get an access token for authentication.
    
    Args:
        db: Database session
        form_data: OAuth2 password request form
        request: Request object
        
    Returns:
        Access token and refresh token
        
    Raises:
        HTTPException: If authentication fails
    """
    logger.info(f"Login attempt for username: {form_data.username}")
    
    # Authenticate user
    user = await UserService.authenticate(db, username=form_data.username, password=form_data.password, request=request)
    
    if not user:
        # Log failed login
        await log_action_async(
            db=db,
            action="LOGIN_FAILED",
            resource_type="USER",
            resource_id=None,
            details={"username": form_data.username, "reason": "invalid_credentials"},
            user_id=None,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
        logger.warning(f"Failed login attempt for username: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Log successful login
    await log_action_async(
        db=db,
        action="LOGIN",
        resource_type="USER",
        resource_id=str(user.id),
        details={"username": user.username},
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.security.access_token_expire_minutes)
    access_token = TokenManager.create_access_token(
        subject=user.username, 
        expires_delta=access_token_expires
    )
    
    # Create refresh token
    refresh_token = TokenManager.create_refresh_token(subject=user.username)
    
    # Store refresh token in Redis with expiration
    refresh_token_key = f"refresh_token:{user.id}"
    await set_cache(
        refresh_token_key,
        refresh_token,
        expire=timedelta(days=settings.security.refresh_token_expire_days)
    )
    
    # Update last login time
    user.last_login = datetime.utcnow()
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Invalidate permission cache on login
    await PermissionCache.invalidate_user_permissions(user.id)
    
    # Create session
    try:
        await create_user_session(db, user, access_token, request)
    except Exception as e:
        logger.error(f"Error creating user session: {e}")
    
    logger.info(f"User logged in successfully: {user.username}")
    return {
        "access_token": access_token, 
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

# Add the token refresh endpoint
@router.post("/refresh")
async def refresh_access_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    refresh_token: str = Form(...),
) -> dict:
    """
    Refresh an access token using a refresh token.
    
    Args:
        request: Request object
        db: Database session
        refresh_token: Refresh token
        
    Returns:
        New access token
        
    Raises:
        HTTPException: If refresh token is invalid or expired
    """
    logger.info("Token refresh attempt")
    
    # Verify the refresh token
    payload = TokenManager.verify_token(refresh_token, "refresh")
    if not payload:
        logger.warning("Invalid refresh token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    username = payload.get("sub")
    if not username:
        logger.warning("Refresh token missing subject")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Get user from database
    result = await db.execute(
        select(UserModel).where(UserModel.username == username)
    )
    user = result.scalars().first()
    
    if not user:
        logger.warning(f"User not found for refresh token: {username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Check if refresh token exists in Redis
    refresh_token_key = f"refresh_token:{user.id}"
    stored_refresh_token = await get_cache(refresh_token_key)
    
    if not stored_refresh_token or stored_refresh_token != refresh_token:
        logger.warning(f"Refresh token not found or mismatch for user: {username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Create new access token
    access_token_expires = timedelta(minutes=settings.security.access_token_expire_minutes)
    new_access_token = TokenManager.create_access_token(
        subject=user.username, 
        expires_delta=access_token_expires
    )
    
    logger.info(f"Access token refreshed successfully for user: {username}")
    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }

@router.get("/me", response_model=UserSchema)
async def read_users_me(
    current_user: UserModel = Depends(get_current_active_user)
) -> Any:
    """Get current user information."""
    return current_user

# Add a logout endpoint that invalidates refresh tokens
@router.post("/logout")
async def logout_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> dict:
    """Logout user and invalidate refresh token."""
    logger.info(f"User logged out: {current_user.username}")
    
    # Invalidate refresh token
    refresh_token_key = f"refresh_token:{current_user.id}"
    await delete_cache(refresh_token_key)
    
    # Log logout action
    await log_action_async(
        db=db,
        action="LOGOUT",
        resource_type="USER",
        resource_id=str(current_user.id),
        details={"username": current_user.username},
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    
    return {"message": "Successfully logged out"}

@router.post("/password-reset-request")
async def request_password_reset(
    request_data: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Request password reset.
    
    Args:
        request_data: Password reset request data
        request: Request object
        db: Database session
        
    Returns:
        Password reset request status message
    """
    logger.info(f"Password reset request for email: {request_data.email}")
    
    result = await db.execute(
        select(UserModel).where(UserModel.email == request_data.email)
    )
    user = result.scalars().first()
    
    if not user:
        logger.info(f"Password reset requested for non-existent email: {request_data.email}")
        return {"message": "If your email is registered, you will receive a password reset link"}
    
    reset_token = secrets.token_urlsafe(32)
    
    user.reset_token = reset_token
    user.reset_token_expires = datetime.utcnow() + timedelta(
        minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
    )
    
    await db.commit()
    
    # Log password reset request
    await log_action_async(
        db=db,
        action="PASSWORD_RESET_REQUEST",
        resource_type="USER",
        resource_id=str(user.id),
        details={"email": user.email},
        user_id=None,
        ip_address=request.client.host,
        user_agent=request.headers.get("User-Agent"),
    )
    
    email_sent = EmailService.send_password_reset_email(user.email, reset_token)
    
    if not email_sent:
        logger.error(f"Failed to send password reset email to {user.email}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send password reset email"
        )
    
    logger.info(f"Password reset email sent to: {user.email}")
    return {"message": "If your email is registered, you will receive a password reset link"}

@router.post("/reset-password")
async def reset_password(
    reset_data: PasswordReset,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Reset password.
    
    Args:
        reset_data: Password reset data
        request: Request object
        db: Database session
        
    Returns:
        Password reset status message
    """
    logger.info("Password reset attempt with token")
    
    result = await db.execute(
        select(UserModel).where(UserModel.reset_token == reset_data.token)
    )
    user = result.scalars().first()
    
    if not user:
        logger.warning("Password reset attempt with invalid token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    if user.reset_token_expires < datetime.utcnow():
        logger.warning("Password reset attempt with expired token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Update password
    user.hashed_password = get_password_hash(reset_data.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    
    await db.commit()
    
    # Log password reset
    await log_action_async(
        db=db,
        action="PASSWORD_RESET",
        resource_type="USER",
        resource_id=str(user.id),
        details={"username": user.username},
        user_id=user.id,
        ip_address=request.client.host,
        user_agent=request.headers.get("User-Agent"),
    )
    
    logger.info(f"Password reset successful for user: {user.username}")
    return {"message": "Password reset successfully"}

@router.put("/profile", response_model=UserSchema)
async def update_user_profile(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user),
    profile_picture: UploadFile = File(None),
    username: str = Form(None),
    email: str = Form(None),
    full_name: str = Form(None),
    role: str = Form(None),
    is_active: bool = Form(None),
    phone: str = Form(None),
    department_id: str = Form(None),  # Changed from department to department_id
    position: str = Form(None),
    bio: str = Form(None),  
) -> UserSchema:
    """
    Update user profile.
    
    Args:
        request: Request object
        db: Database session
        current_user: Current user
        profile_picture: Profile picture file
        username: Username
        email: Email
        full_name: Full name
        role: Role
        is_active: Is active
        phone: Phone
        department_id: Department ID  # Changed from department to department_id
        position: Position
        bio: Bio
        
    Returns:
        Updated user profile
    """
    logger.info(f"Profile update attempt by user: {current_user.username}")
    
    user_update_data = {}
    if username is not None:
        user_update_data["username"] = username
    if email is not None:
        user_update_data["email"] = email
    if full_name is not None:
        user_update_data["full_name"] = full_name
    if role is not None:
        user_update_data["role"] = role
    if is_active is not None:
        user_update_data["is_active"] = is_active
    if phone is not None:
        user_update_data["phone"] = phone
    if department_id is not None:
        # Handle department field properly - it should be a UUID
        try:
            # Try to convert to UUID if it's a valid UUID string
            department_uuid = UUID(department_id)
            user_update_data["department_id"] = department_uuid
        except ValueError:
            # If not a valid UUID, try to find department by name
            from app.models.department import Department
            result = await db.execute(
                select(Department).where(Department.name == department_id)
            )
            dept = result.scalars().first()
            if dept:
                user_update_data["department_id"] = dept.id
            else:
                logger.warning(f"Department not found: {department_id}")
                # Skip updating department if not found
    if position is not None:
        user_update_data["position"] = position
    if bio is not None:
        user_update_data["bio"] = bio
    
    # Handle profile picture upload
    if profile_picture:
        try:
            uploads_dir = Path("uploads/profile_pictures")
            uploads_dir.mkdir(parents=True, exist_ok=True)
            
            file_extension = profile_picture.filename.split('.')[-1] if '.' in profile_picture.filename else 'jpg'
            unique_filename = f"{uuid4()}.{file_extension}"
            file_path = uploads_dir / unique_filename
            
            with open(file_path, "wb") as buffer:
                chunk_size = 1024 * 1024
                while chunk := await profile_picture.read(chunk_size):
                    buffer.write(chunk)
            
            base_url = str(request.base_url)
            user_update_data["profile_picture_url"] = f"{base_url}uploads/profile_pictures/{unique_filename}"
        except Exception as e:
            logger.error(f"Failed to upload profile picture: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload profile picture: {str(e)}"
            )
    
    user_update = UserUpdate(**user_update_data)
    
    user = await UserService.update(
        db=db,
        user_id=current_user.id,
        user_in=user_update,
        request=request,
        acting_user_id=current_user.id
    )
    
    if not user:
        logger.error(f"Failed to update profile for user: {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    logger.info(f"Profile updated successfully for user: {current_user.username}")
    return user

@router.get("/profile", response_model=UserSchema)
async def get_user_profile(
    current_user: UserModel = Depends(get_current_active_user)
) -> UserSchema:
    """
    Get current user's profile.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current user's profile
    """
    return current_user

@router.post("/change-password")
async def change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> dict:
    """
    Change current user's password.
    
    Args:
        current_password: Current password
        new_password: New password
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If password change fails
    """
    logger.info(f"Password change attempt by user: {current_user.username}")
    
    if not verify_password(current_password, current_user.hashed_password):
        await log_action_async(
            db=db,
            action="PASSWORD_CHANGE_FAILED",
            resource_type="USER",
            resource_id=str(current_user.id),
            details={"reason": "current_password_incorrect"},
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
        logger.warning(f"Failed password change attempt by user: {current_user.username} - incorrect current password")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    current_user.hashed_password = get_password_hash(new_password)
    await db.commit()
    
    await log_action_async(
        db=db,
        action="PASSWORD_CHANGE",
        resource_type="USER",
        resource_id=str(current_user.id),
        details={"username": current_user.username},
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    
    logger.info(f"Password changed successfully for user: {current_user.username}")
    return {"message": "Password changed successfully"}
