"""
Service layer for user operations.

This module contains the business logic for user-related operations,
abstracting away the database operations from the API endpoints.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import verify_password, get_password_hash
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.email import EmailService
from app.core.logging import logger
from app.db.audit import log_action_async  
from fastapi import Request 
from app.core.rbac import PermissionCache, Role

class UserService:
    """Service class for user operations."""

    @staticmethod
    async def create(
        db: AsyncSession,
        user_in: UserCreate,
        request: Request,          
        acting_user_id: Optional[UUID] = None
    ) -> User:
        """
        Create a new user and log the action.

        Args:
            db: Database session
            user_in: User creation data
            request: FastAPI request (for IP and User-Agent)
            acting_user_id: ID of admin/user performing the action. None = self-registration

        Returns:
            Created user
        """
        logger.info(f"Creating new user: {user_in.username}")
        
        # Create user with hashed password
        user_data = user_in.dict()
        password = user_data.pop("password")
        user_data["hashed_password"] = get_password_hash(password)
        user = User(**user_data)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # Log audit
        await log_action_async(
            db=db,
            action="CREATE",
            resource_type="USER",
            resource_id=str(user.id),
            details={
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active
            },
            user_id=acting_user_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent")
        )
        
        # Send welcome email
        try:
            await EmailService.send_welcome_email(user.email, user.username)
            logger.info(f"Welcome email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send welcome email to {user.email}: {e}")
        
        return user

    @staticmethod
    async def authenticate(
        db: AsyncSession,
        username: str,
        password: str,
        request: Request
    ) -> Optional[User]:
        """
        Authenticate a user and log successful login.

        Args:
            db: Database session
            username: Username
            password: Password
            request: FastAPI request

        Returns:
            User if authentication succeeds, None otherwise
        """
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalars().first()
        if not user:
            logger.warning(f"Authentication failed: User not found - {username}")
            return None
        
        if not verify_password(password, user.hashed_password):
            logger.warning(f"Authentication failed: Invalid password for user - {username}")
            return None

        # Log successful login
        await log_action_async(
            db=db,
            action="LOGIN",
            resource_type="USER",
            resource_id=str(user.id),
            details={"username": user.username, "success": True},
            user_id=user.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent")
        )

        return user

    @staticmethod
    async def update(
        db: AsyncSession,
        user_id: UUID,
        user_in: UserUpdate,
        request: Request,
        acting_user_id: Optional[UUID] = None
    ) -> Optional[User]:
        """
        Update a user and log changes.

        Args:
            db: Database session
            user_id: User ID to update
            user_in: Update data
            request: FastAPI request
            acting_user_id: Who is making the change

        Returns:
            Updated user or None
        """
        user = await UserService.get_by_id(db, user_id)
        if not user:
            return None
        
        old_data = {
            k: getattr(user, k)
            for k in user_in.dict(exclude_unset=True).keys()
            if hasattr(user, k)
        }
        
        update_data = user_in.dict(exclude_unset=True)
        role_changed = False
        
        if "password" in update_data:
            password = update_data.pop("password")
            update_data["hashed_password"] = get_password_hash(password)
        
        if "role" in update_data and update_data["role"] != user.role:
            role_changed = True
            old_role = user.role
            new_role = update_data["role"]
        
        for field, value in update_data.items():
            setattr(user, field, value)
        
        await db.commit()
        await db.refresh(user)
        
        # Log update with diff
        changed_fields = {
            k: {"old": old_data[k], "new": value}
            for k, value in update_data.items()
            if old_data.get(k) != value
        }
        
        if changed_fields:
            await log_action_async(
                db=db,
                action="UPDATE",
                resource_type="USER",
                resource_id=str(user.id),
                details={"changed_fields": changed_fields},
                user_id=acting_user_id or user.id,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("User-Agent")
            )
        
        # Invalidate permission cache if role changed
        if role_changed:
            await PermissionCache.invalidate_user_permissions(user_id)
            logger.info(f"User role changed from {old_role} to {new_role} for user {user.username}")
            
            # Send role change notification email
            try:
                await EmailService.send_role_change_email(user.email, user.username, old_role, new_role)
                logger.info(f"Role change notification sent to {user.email}")
            except Exception as e:
                logger.error(f"Failed to send role change email to {user.email}: {e}")
        
        return user

    @staticmethod
    async def delete(
        db: AsyncSession,
        user_id: UUID,
        request: Request,
        acting_user_id: UUID  # Must be admin or system
    ) -> bool:
        """
        Delete a user and log deletion.

        Args:
            db: Database session
            user_id: ID of user to delete
            request: FastAPI request
            acting_user_id: Admin/user performing deletion

        Returns:
            True if deleted, False otherwise
        """
        user = await UserService.get_by_id(db, user_id)
        if not user:
            return False
        
        # Capture data before delete
        user_data = {
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active
        }
        
        await db.delete(user)
        await db.commit()
        
        # Log deletion
        await log_action_async(
            db=db,
            action="DELETE",
            resource_type="USER",
            resource_id=str(user.id),
            details=user_data,
            user_id=acting_user_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent")
        )
        
        # Send account deletion email
        try:
            await EmailService.send_account_deletion_email(user.email, user.username)
            logger.info(f"Account deletion notification sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send account deletion email to {user.email}: {e}")
        
        return True
    
    # -------------------------------
    # READ-ONLY METHODS (no audit)
    # -------------------------------

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalars().first()
    
    @staticmethod
    async def get_by_username(db: AsyncSession, username: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalars().first()
    
    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalars().first()