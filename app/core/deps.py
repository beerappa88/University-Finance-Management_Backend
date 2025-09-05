"""
Dependencies for FastAPI endpoints.

This module provides dependencies for authentication and authorization.
"""

from typing import Optional, Generator
from fastapi import Depends, HTTPException, status, Request, Query
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.core.rbac import Role, Permission, require_permission, PermissionCache
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import TokenData
from app.core.logging import logger
from app.core.cache import get_cache as redis_get, set_cache as redis_set, delete_cache as redis_delete
from app.core.auth import get_current_active_user
from app.core.rbac import (
    # Basic permission dependencies
    can_create_user, can_read_user, can_update_user, can_delete_user,
    can_create_department, can_read_department, can_update_department, can_delete_department,
    can_create_budget, can_read_budget, can_update_budget, can_delete_budget,
    can_create_transaction, can_read_transaction, can_update_transaction, can_delete_transaction,
    can_create_report, can_read_report, can_delete_report,
    can_read_audit, can_manage_audit,
    
    # Resource-aware dependencies for getting resources
    get_department_with_access, get_budget_with_access, get_transaction_with_access,
    
    # Resource-aware dependencies for modifying resources
    update_department_with_access, delete_department_with_access,
    update_budget_with_access, delete_budget_with_access,
    update_transaction_with_access, delete_transaction_with_access,
    update_user_with_access, delete_user_with_access
)
from app.utils.pagination import PaginationParams

def get_pagination_params(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search term"),
    sort_by: str = Query("id", description="Field to sort by"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort order")
) -> PaginationParams:
    """
    Get pagination parameters from request query.
    
    Returns:
        PaginationParams object with extracted values
    """
    return PaginationParams(
        page=page,
        size=size,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order
    )


async def get_request_client(request: Request):
    """Extract client information from request."""
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent")
    }

def require_role(required_role: str):
    """
    Create a dependency to check if user has required role.
    
    Args:
        required_role: Required role
        
    Returns:
        Dependency function
    """
    async def role_dependency(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        """
        Check if user has required role.
        
        Args:
            current_user: Current authenticated user
            
        Returns:
            Current user if they have the required role
            
        Raises:
            HTTPException: If user doesn't have the required role
        """
        user_role = Role(current_user.role)
        if user_role != Role(required_role) and user_role != Role.ADMIN:
            logger.warning(
                f"Role access denied: User {current_user.username} ({user_role.value}) "
                f"attempted to access role-restricted resource requiring {required_role}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
    return role_dependency
