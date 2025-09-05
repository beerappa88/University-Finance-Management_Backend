# rabc.py
"""
Enhanced Role-Based Access Control (RBAC) 
utilities with hierarchical 
roles and resource-based access control.
"""
from enum import Enum
from typing import Set, Dict, List, Optional, Any, Callable, Union
from uuid import UUID
from fastapi import HTTPException, status, Depends, Request, Path
from app.models.user import User
from app.core.auth import get_current_active_user
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.cache import get_cache as redis_get, set_cache as redis_set, delete_cache as redis_delete
from app.core.logging import logger
from datetime import datetime, timedelta
import json

class Role(Enum):
    """User roles with hierarchical structure."""
    ADMIN = "admin"
    FINANCE_MANAGER = "finance_manager"
    DEPARTMENT_HEAD = "department_head"
    VIEWER = "viewer"

class Permission(Enum):
    """System permissions with resource-action structure."""
    # User permissions
    CREATE_USER = "create_user"
    READ_USER = "read_user"
    UPDATE_USER = "update_user"
    DELETE_USER = "delete_user"
    
    # Department permissions
    CREATE_DEPARTMENT = "create_department"
    READ_DEPARTMENT = "read_department"
    UPDATE_DEPARTMENT = "update_department"
    DELETE_DEPARTMENT = "delete_department"
    
    # Budget permissions
    CREATE_BUDGET = "create_budget"
    READ_BUDGET = "read_budget"
    UPDATE_BUDGET = "update_budget"
    DELETE_BUDGET = "delete_budget"
    
    # Transaction permissions
    CREATE_TRANSACTION = "create_transaction"
    READ_TRANSACTION = "read_transaction"
    UPDATE_TRANSACTION = "update_transaction"
    DELETE_TRANSACTION = "delete_transaction"
    
    # Report permissions
    CREATE_REPORT = "create_report"
    READ_REPORT = "read_report"
    DELETE_REPORT = "delete_report"
    
    # Audit permissions
    READ_AUDIT = "read_audit"
    MANAGE_AUDIT = "manage_audit"

# Role hierarchy: higher roles inherit permissions of lower roles
ROLE_HIERARCHY: Dict[Role, Set[Role]] = {
    Role.ADMIN: {
        Role.FINANCE_MANAGER, 
        Role.DEPARTMENT_HEAD, 
        Role.VIEWER
    },
    Role.FINANCE_MANAGER: {
        Role.DEPARTMENT_HEAD, 
        Role.VIEWER
    },
    Role.DEPARTMENT_HEAD: {
        Role.VIEWER
    },
    Role.VIEWER: set()
}

# Base permissions for each role
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        # Admin has all permissions
        Permission.CREATE_USER, Permission.READ_USER, Permission.UPDATE_USER, Permission.DELETE_USER,
        Permission.CREATE_DEPARTMENT, Permission.READ_DEPARTMENT, Permission.UPDATE_DEPARTMENT, Permission.DELETE_DEPARTMENT,
        Permission.CREATE_BUDGET, Permission.READ_BUDGET, Permission.UPDATE_BUDGET, Permission.DELETE_BUDGET,
        Permission.CREATE_TRANSACTION, Permission.READ_TRANSACTION, Permission.UPDATE_TRANSACTION, Permission.DELETE_TRANSACTION,
        Permission.CREATE_REPORT, Permission.READ_REPORT, Permission.DELETE_REPORT,
        Permission.READ_AUDIT, Permission.MANAGE_AUDIT
    },
    Role.FINANCE_MANAGER: {
        Permission.READ_USER,
        Permission.CREATE_DEPARTMENT, Permission.READ_DEPARTMENT, Permission.UPDATE_DEPARTMENT, Permission.DELETE_DEPARTMENT,
        Permission.CREATE_BUDGET, Permission.READ_BUDGET, Permission.UPDATE_BUDGET, Permission.DELETE_BUDGET,
        Permission.CREATE_TRANSACTION, Permission.READ_TRANSACTION, Permission.UPDATE_TRANSACTION, Permission.DELETE_TRANSACTION,
        Permission.CREATE_REPORT, Permission.READ_REPORT
    },
    Role.DEPARTMENT_HEAD: {
        Permission.READ_USER,
        Permission.READ_DEPARTMENT,
        Permission.CREATE_BUDGET, Permission.READ_BUDGET, Permission.UPDATE_BUDGET,
        Permission.CREATE_TRANSACTION, Permission.READ_TRANSACTION, Permission.UPDATE_TRANSACTION,
        Permission.READ_REPORT
    },
    Role.VIEWER: {
        Permission.READ_USER,
        Permission.READ_DEPARTMENT,
        Permission.READ_BUDGET,
        Permission.READ_TRANSACTION,
        Permission.READ_REPORT
    }
}

def get_effective_permissions(role: Role) -> Set[Permission]:
    """
    Get effective permissions for a role, including inherited permissions.
    
    Args:
        role: User role
        
    Returns:
        Set of permission names
    """
    permissions = set(ROLE_PERMISSIONS.get(role, set()))
    for inherited_role in ROLE_HIERARCHY.get(role, set()):
        permissions.update(ROLE_PERMISSIONS.get(inherited_role, set()))
    return permissions

def has_permission(user_role: Role, permission: Permission) -> bool:
    """
    Check if a role has a specific permission.
    
    Args:
        user_role: User role
        permission: Permission to check
        
    Returns:
        True if role has permission, False otherwise
    """
    return permission in get_effective_permissions(user_role)

# Resource-based access control
class ResourcePolicy:
    """Resource-based access control policies."""
    
    @staticmethod
    def can_access_department(user_role: Role, user_department_id: Optional[UUID], target_department_id: UUID) -> bool:
        """
        Check if user can access a department.
        
        Args:
            user_role: User role
            user_department_id: User's department ID
            target_department_id: Target department ID
            
        Returns:
            True if user can access department, False otherwise
        """
        if user_role == Role.ADMIN:
            return True
        if user_role == Role.FINANCE_MANAGER:
            return True
        if user_role == Role.DEPARTMENT_HEAD:
            return user_department_id == target_department_id
        if user_role == Role.VIEWER:
            return user_department_id == target_department_id
        return False
    
    @staticmethod
    def can_modify_user(user_role: Role, current_user_id: UUID, target_user_id: UUID) -> bool:
        """
        Check if user can modify a user.
        
        Args:
            user_role: User role
            current_user_id: Current user ID
            target_user_id: Target user ID
            
        Returns:
            True if user can modify user, False otherwise
        """
        if user_role == Role.ADMIN:
            return True
        # Users can modify their own account
        return current_user_id == target_user_id
    
    @staticmethod
    def can_manage_budget(user_role: Role, user_department_id: Optional[UUID], budget_department_id: UUID) -> bool:
        """
        Check if user can manage a budget.
        
        Args:
            user_role: User role
            user_department_id: User's department ID
            budget_department_id: Budget's department ID
            
        Returns:
            True if user can manage budget, False otherwise
        """
        if user_role == Role.ADMIN:
            return True
        if user_role == Role.FINANCE_MANAGER:
            return True
        if user_role == Role.DEPARTMENT_HEAD:
            return user_department_id == budget_department_id
        return False
    
    @staticmethod
    def can_manage_transaction(user_role: Role, user_department_id: Optional[UUID], transaction_budget_department_id: UUID) -> bool:
        """
        Check if user can manage a transaction.
        
        Args:
            user_role: User role
            user_department_id: User's department ID
            transaction_budget_department_id: Transaction's budget's department ID
            
        Returns:
            True if user can manage transaction, False otherwise
        """
        if user_role == Role.ADMIN:
            return True
        if user_role == Role.FINANCE_MANAGER:
            return True
        if user_role == Role.DEPARTMENT_HEAD:
            return user_department_id == transaction_budget_department_id
        return False

# Permission caching system with Redis
class PermissionCache:
    """Cache user permissions using Redis to reduce database hits."""
    
    @staticmethod
    async def get_user_permissions(user_id: UUID, user_role: Role) -> Set[Permission]:
        """
        Get cached permissions for a user.
        
        Args:
            user_id: User ID
            user_role: User role
            
        Returns:
            Set of permission names
        """
        cache_key = f"user_permissions:{user_id}"
        cached = await redis_get(cache_key, use_json=True)
        
        if cached:
            try:
                return set(Permission(p) for p in cached)
            except (ValueError, TypeError):
                # Cache corruption, clear it
                await redis_delete(cache_key)
                logger.warning(f"Cache corruption detected for user {user_id}, clearing cache")
        
        # Cache miss - get from role
        permissions = get_effective_permissions(user_role)
        
        # Cache for 1 hour
        await redis_set(
            cache_key,
            [p.value for p in permissions],
            expire=timedelta(seconds=3600),
            use_json=True
        )
        
        logger.debug(f"Cached permissions for user {user_id}: {[p.value for p in permissions]}")
        return permissions
    
    @staticmethod
    async def invalidate_user_permissions(user_id: UUID):
        """
        Invalidate cached permissions for a user.
        
        Args:
            user_id: User ID
        """
        cache_key = f"user_permissions:{user_id}"
        await redis_delete(cache_key)
        logger.info(f"Invalidated permission cache for user {user_id}")

def require_permission(permission: Permission):
    """
    Create a dependency to check if user has required permission.
    
    Args:
        permission: Required permission
        
    Returns:
        Dependency function
    """
    async def permission_dependency(current_user: User = Depends(get_current_active_user)):
        """
        Check if user has required permission.
        
        Args:
            current_user: Current authenticated user
            
        Returns:
            Current user if they have the required permission
            
        Raises:
            HTTPException: If user doesn't have the required permission
        """
        user_role = Role(current_user.role)
        if not has_permission(user_role, permission):
            # Log permission denial
            logger.warning(
                f"Permission denied: User {current_user.username} ({user_role.value}) "
                f"attempted to access {permission.value}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    
    return permission_dependency

def require_permission_with_resource(
    permission: Permission,
    resource_checker: Callable[[User, Any], bool]
):
    """
    Create a dependency to check if user has required permission and resource access.
    
    Args:
        permission: Required permission
        resource_checker: Function to check resource access
        
    Returns:
        Dependency function
    """
    async def permission_dependency(current_user: User = Depends(get_current_active_user), *args, **kwargs):
        user_role = Role(current_user.role)
        if not has_permission(user_role, permission):
            logger.warning(
                f"Permission denied: User {current_user.username} ({user_role.value}) "
                f"attempted to access {permission.value}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        # Check resource access
        if not await resource_checker(current_user, *args, **kwargs):
            logger.warning(
                f"Resource access denied: User {current_user.username} ({user_role.value}) "
                f"attempted to access restricted resource"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this resource"
            )
        return current_user
    return permission_dependency

# Resource checkers
async def check_department_access(department_id: UUID, current_user: User) -> bool:
    """
    Check if user has access to a department.
    
    Args:
        department_id: Department ID
        current_user: Current authenticated user
        
    Returns:
        True if user has access to the department, False otherwise
    """
    return ResourcePolicy.can_access_department(
        Role(current_user.role),
        current_user.department_id,
        department_id
    )

async def check_budget_access(db: AsyncSession, budget_id: UUID, current_user: User) -> bool:
    """
    Check if user has access to a budget.
    
    Args:
        db: Database session
        budget_id: Budget ID
        current_user: Current authenticated user
        
    Returns:
        True if user has access to the budget, False otherwise
    """
    from app.services.budget import BudgetService
    budget = await BudgetService.get_by_id(db, budget_id)
    if not budget:
        return False
    return ResourcePolicy.can_manage_budget(
        Role(current_user.role),
        current_user.department_id,
        budget.department_id
    )

async def check_transaction_access(db: AsyncSession, transaction_id: UUID, current_user: User) -> bool:
    """
    Check if user has access to a transaction.
    
    Args:
        db: Database session
        transaction_id: Transaction ID
        current_user: Current authenticated user
        
    Returns:
        True if user has access to the transaction, False otherwise
    """
    from app.services.transaction import TransactionService
    from app.services.budget import BudgetService
    transaction = await TransactionService.get_by_id(db, transaction_id)
    if not transaction:
        return False
    budget = await BudgetService.get_by_id(db, transaction.budget_id)
    if not budget:
        return False
    return ResourcePolicy.can_manage_transaction(
        Role(current_user.role),
        current_user.department_id,
        budget.department_id
    )

async def check_user_access(target_user_id: UUID, current_user: User) -> bool:
    """
    Check if user has access to a user.
    
    Args:
        target_user_id: Target user ID
        current_user: Current authenticated user
        
    Returns:
        True if user has access to the user, False otherwise
    """
    return ResourcePolicy.can_modify_user(
        Role(current_user.role),
        current_user.id,
        target_user_id
    )

# Specific resource dependencies
async def get_department_with_access(
    department_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """Get department with access check."""
    from app.services.department import DepartmentService
    department = await DepartmentService.get_by_id(db, department_id)
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    if not await check_department_access(department_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this department"
        )
    
    return department

async def update_department_with_access(
    department_id: UUID = Path(...),
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Check department update access."""
    if not await check_department_access(department_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this department"
        )
    return current_user

async def delete_department_with_access(
    department_id: UUID = Path(...),
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Check department delete access."""
    if not await check_department_access(department_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this department"
        )
    return current_user

async def get_budget_with_access(
    budget_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """Get budget with access check."""
    from app.services.budget import BudgetService
    budget = await BudgetService.get_by_id(db, budget_id)
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    
    if not await check_budget_access(db, budget_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this budget"
        )
    
    return budget

async def update_budget_with_access(
    budget_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Check budget update access."""
    if not await check_budget_access(db, budget_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this budget"
        )
    return current_user

async def delete_budget_with_access(
    budget_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Check budget delete access."""
    if not await check_budget_access(db, budget_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this budget"
        )
    return current_user

async def get_transaction_with_access(
    transaction_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """Get transaction with access check."""
    from app.services.transaction import TransactionService
    transaction = await TransactionService.get_by_id(db, transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    if not await check_transaction_access(db, transaction_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this transaction"
        )
    
    return transaction

async def update_transaction_with_access(
    transaction_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Check transaction update access."""
    if not await check_transaction_access(db, transaction_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this transaction"
        )
    return current_user

async def delete_transaction_with_access(
    transaction_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Check transaction delete access."""
    if not await check_transaction_access(db, transaction_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this transaction"
        )
    return current_user

async def update_user_with_access(
    user_id: UUID = Path(...),
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Check user update access."""
    if not await check_user_access(user_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this user"
        )
    return current_user

async def delete_user_with_access(
    user_id: UUID = Path(...),
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Check user delete access."""
    if not await check_user_access(user_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this user"
        )
    return current_user

# Basic permission dependencies
can_create_user = require_permission(Permission.CREATE_USER)
can_read_user = require_permission(Permission.READ_USER)
can_update_user = require_permission(Permission.UPDATE_USER)
can_delete_user = require_permission(Permission.DELETE_USER)
can_create_department = require_permission(Permission.CREATE_DEPARTMENT)
can_read_department = require_permission(Permission.READ_DEPARTMENT)
can_update_department = require_permission(Permission.UPDATE_DEPARTMENT)
can_delete_department = require_permission(Permission.DELETE_DEPARTMENT)
can_create_budget = require_permission(Permission.CREATE_BUDGET)
can_read_budget = require_permission(Permission.READ_BUDGET)
can_update_budget = require_permission(Permission.UPDATE_BUDGET)
can_delete_budget = require_permission(Permission.DELETE_BUDGET)
can_create_transaction = require_permission(Permission.CREATE_TRANSACTION)
can_read_transaction = require_permission(Permission.READ_TRANSACTION)
can_update_transaction = require_permission(Permission.UPDATE_TRANSACTION)
can_delete_transaction = require_permission(Permission.DELETE_TRANSACTION)
can_create_report = require_permission(Permission.CREATE_REPORT)
can_read_report = require_permission(Permission.READ_REPORT)
can_delete_report = require_permission(Permission.DELETE_REPORT)
can_read_audit = require_permission(Permission.READ_AUDIT)
can_manage_audit = require_permission(Permission.MANAGE_AUDIT)

# Removed ROLE_RATE_LIMITS