# """
# Audit logging utilities.

# This module provides utilities for creating audit logs and setting up
# event listeners for automatic logging.
# """

# from typing import Any, Dict, Optional
# from datetime import datetime
# import json
# import uuid

# from sqlalchemy import event
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.orm import Session
# from sqlalchemy.orm.attributes import get_history

# from app.models.audit import AuditLog
# from app.models.user import User
# from app.models.department import Department
# from app.models.budget import Budget
# from app.models.transaction import Transaction, TransactionType
# from app.core.logging import logger


# def serialize_for_json(obj):
#     """
#     Convert an object to a JSON-serializable format.
    
#     Args:
#         obj: Object to serialize
        
#     Returns:
#         JSON-serializable representation of the object
#     """
#     if obj is None:
#         return None
#     if isinstance(obj, uuid.UUID):
#         return str(obj)
#     if isinstance(obj, (int, float, str, bool)):
#         return obj
#     if isinstance(obj, dict):
#         return {k: serialize_for_json(v) for k, v in obj.items()}
#     if isinstance(obj, (list, tuple)):
#         return [serialize_for_json(item) for item in obj]
#     return str(obj)


# def log_action(
#     db: Session,
#     action: str,
#     resource_type: str,
#     resource_id: Optional[str] = None,
#     details: Optional[Dict[str, Any]] = None,
#     user_id: Optional[int] = None,
#     ip_address: Optional[str] = None,
#     user_agent: Optional[str] = None
# ) -> AuditLog:
#     """
#     Create an audit log entry.
    
#     Args:
#         db: Database session
#         action: Action performed (CREATE, UPDATE, DELETE, etc.)
#         resource_type: Type of resource affected
#         resource_id: ID of the resource affected
#         details: Additional details about the action
#         user_id: ID of the user who performed the action
#         ip_address: IP address of the user
#         user_agent: User agent string
        
#     Returns:
#         Created audit log entry
#     """
#     logger.debug(f"Creating audit log: {action} on {resource_type}")
    
#     # Serialize details for JSON storage
#     serialized_details = serialize_for_json(details) if details else None
    
#     audit_log = AuditLog(
#         user_id=user_id,
#         action=action,
#         resource_type=resource_type,
#         resource_id=resource_id,
#         details=serialized_details,
#         ip_address=ip_address,
#         user_agent=user_agent
#     )
    
#     db.add(audit_log)
#     db.commit()
#     db.refresh(audit_log)
    
#     return audit_log


# async def log_action_async(
#     db: AsyncSession,
#     action: str,
#     resource_type: str,
#     resource_id: Optional[str] = None,
#     details: Optional[Dict[str, Any]] = None,
#     user_id: Optional[int] = None,
#     ip_address: Optional[str] = None,
#     user_agent: Optional[str] = None
# ) -> AuditLog:
#     """
#     Create an audit log entry asynchronously.
    
#     Args:
#         db: Database session
#         action: Action performed (CREATE, UPDATE, DELETE, etc.)
#         resource_type: Type of resource affected
#         resource_id: ID of the resource affected
#         details: Additional details about the action
#         user_id: ID of the user who performed the action
#         ip_address: IP address of the user
#         user_agent: User agent string
        
#     Returns:
#         Created audit log entry
#     """
#     logger.debug(f"Creating audit log async: {action} on {resource_type}")
    
#     # Serialize details for JSON storage
#     serialized_details = serialize_for_json(details) if details else None
    
#     audit_log = AuditLog(
#         user_id=user_id,
#         action=action,
#         resource_type=resource_type,
#         resource_id=resource_id,
#         details=serialized_details,
#         ip_address=ip_address,
#         user_agent=user_agent
#     )
    
#     db.add(audit_log)
#     await db.commit()
#     await db.refresh(audit_log)
    
#     return audit_log


# def setup_audit_event_listeners():
#     """Set up SQLAlchemy event listeners for automatic audit logging."""
    
#     @event.listens_for(User, 'after_insert')
#     def log_user_insert(mapper, connection, target):
#         """Log user creation."""
#         session = Session(bind=connection)
#         log_action(
#             session,
#             action="CREATE",
#             resource_type="USER",
#             resource_id=str(target.id),
#             details={
#                 "username": target.username,
#                 "email": target.email,
#                 "role": target.role
#             },
#             user_id=None  # User self-registration, no user context
#         )
#         session.close()
    
#     @event.listens_for(User, 'after_update')
#     def log_user_update(mapper, connection, target):
#         """Log user updates."""
#         # Get changes using SQLAlchemy's get_history
#         changes = {}
#         for attr in mapper.attrs:
#             if not attr.key.startswith('_'):
#                 hist = get_history(target, attr.key)
#                 if hist.has_changes():
#                     changes[attr.key] = {
#                         "old": serialize_for_json(hist.deleted[0]) if hist.deleted else None,
#                         "new": serialize_for_json(hist.added[0]) if hist.added else None
#                     }
        
#         if changes:
#             session = Session(bind=connection)
#             log_action(
#                 session,
#                 action="UPDATE",
#                 resource_type="USER",
#                 resource_id=str(target.id),
#                 details=changes,
#                 user_id=None  # User self-update, no user context
#             )
#             session.close()
    
#     @event.listens_for(Department, 'after_insert')
#     def log_department_insert(mapper, connection, target):
#         """Log department creation."""
#         session = Session(bind=connection)
#         log_action(
#             session,
#             action="CREATE",
#             resource_type="DEPARTMENT",
#             resource_id=str(target.id),
#             details={
#                 "name": target.name,
#                 "code": target.code
#             }
#         )
#         session.close()
    
#     @event.listens_for(Department, 'after_update')
#     def log_department_update(mapper, connection, target):
#         """Log department updates."""
#         # Get changes
#         changes = {}
#         for attr in mapper.attrs:
#             if not attr.key.startswith('_'):
#                 hist = get_history(target, attr.key)
#                 if hist.has_changes():
#                     changes[attr.key] = {
#                         "old": serialize_for_json(hist.deleted[0]) if hist.deleted else None,
#                         "new": serialize_for_json(hist.added[0]) if hist.added else None
#                     }
        
#         if changes:
#             session = Session(bind=connection)
#             log_action(
#                 session,
#                 action="UPDATE",
#                 resource_type="DEPARTMENT",
#                 resource_id=str(target.id),
#                 details=changes
#             )
#             session.close()
    
#     @event.listens_for(Department, 'after_delete')
#     def log_department_delete(mapper, connection, target):
#         """Log department deletion."""
#         session = Session(bind=connection)
#         log_action(
#             session,
#             action="DELETE",
#             resource_type="DEPARTMENT",
#             resource_id=str(target.id),
#             details={
#                 "name": target.name,
#                 "code": target.code
#             }
#         )
#         session.close()
    
#     @event.listens_for(Budget, 'after_insert')
#     def log_budget_insert(mapper, connection, target):
#         """Log budget creation."""
#         session = Session(bind=connection)
#         log_action(
#             session,
#             action="CREATE",
#             resource_type="BUDGET",
#             resource_id=str(target.id),
#             details={
#                 "department_id": target.department_id,
#                 "fiscal_year": target.fiscal_year,
#                 "total_amount": str(target.total_amount)
#             }
#         )
#         session.close()
    
#     @event.listens_for(Budget, 'after_update')
#     def log_budget_update(mapper, connection, target):
#         """Log budget updates."""
#         # Get changes
#         changes = {}
#         for attr in mapper.attrs:
#             if not attr.key.startswith('_'):
#                 hist = get_history(target, attr.key)
#                 if hist.has_changes():
#                     changes[attr.key] = {
#                         "old": serialize_for_json(hist.deleted[0]) if hist.deleted else None,
#                         "new": serialize_for_json(hist.added[0]) if hist.added else None
#                     }
        
#         if changes:
#             session = Session(bind=connection)
#             log_action(
#                 session,
#                 action="UPDATE",
#                 resource_type="BUDGET",
#                 resource_id=str(target.id),
#                 details=changes
#             )
#             session.close()
    
#     @event.listens_for(Budget, 'after_delete')
#     def log_budget_delete(mapper, connection, target):
#         """Log budget deletion."""
#         session = Session(bind=connection)
#         log_action(
#             session,
#             action="DELETE",
#             resource_type="BUDGET",
#             resource_id=str(target.id),
#             details={
#                 "department_id": target.department_id,
#                 "fiscal_year": target.fiscal_year,
#                 "total_amount": str(target.total_amount)
#             }
#         )
#         session.close()
    
#     @event.listens_for(Transaction, 'after_insert')
#     def log_transaction_insert(mapper, connection, target):
#         """Log transaction creation."""
#         session = Session(bind=connection)
#         log_action(
#             session,
#             action="CREATE",
#             resource_type="TRANSACTION",
#             resource_id=str(target.id),
#             details={
#                 "budget_id": target.budget_id,
#                 "transaction_type": target.transaction_type.value,
#                 "amount": str(target.amount),
#                 "description": target.description,
#                 "reference_number": target.reference_number
#             }
#         )
#         session.close()
    
#     @event.listens_for(Transaction, 'after_update')
#     def log_transaction_update(mapper, connection, target):
#         """Log transaction updates."""
#         # Get changes
#         changes = {}
#         for attr in mapper.attrs:
#             if not attr.key.startswith('_'):
#                 hist = get_history(target, attr.key)
#                 if hist.has_changes():
#                     changes[attr.key] = {
#                         "old": serialize_for_json(hist.deleted[0]) if hist.deleted else None,
#                         "new": serialize_for_json(hist.added[0]) if hist.added else None
#                     }
        
#         if changes:
#             session = Session(bind=connection)
#             log_action(
#                 session,
#                 action="UPDATE",
#                 resource_type="TRANSACTION",
#                 resource_id=str(target.id),
#                 details=changes
#             )
#             session.close()
    
#     @event.listens_for(Transaction, 'after_delete')
#     def log_transaction_delete(mapper, connection, target):
#         """Log transaction deletion."""
#         session = Session(bind=connection)
#         log_action(
#             session,
#             action="DELETE",
#             resource_type="TRANSACTION",
#             resource_id=str(target.id),
#             details={
#                 "budget_id": target.budget_id,
#                 "transaction_type": target.transaction_type.value,
#                 "amount": str(target.amount),
#                 "description": target.description,
#                 "reference_number": target.reference_number
#             }
#         )
#         session.close()


"""
Audit logging utilities.

This module provides utilities for creating audit logs and setting up
event listeners for automatic logging.
"""

from typing import Any, Dict, Optional
from datetime import datetime
import uuid

from sqlalchemy import event, select, or_, func, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import get_history

from app.models.audit import AuditLog
from app.models.user import User
from app.models.department import Department
from app.models.budget import Budget
from app.models.transaction import Transaction, TransactionType
from app.core.logging import logger


def serialize_for_json(obj: Any) -> Any:
    """
    Convert an object to a JSON-serializable format.

    Args:
        obj: Object to serialize

    Returns:
        JSON-serializable representation of the object
    """
    if obj is None:
        return None
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, (int, float, str, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def log_action(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    user_id: Optional[uuid.UUID] = None,  # ← Now UUID
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AuditLog:
    """
    Create an audit log entry synchronously.

    Args:
        db: Database session
        action: Action performed (CREATE, UPDATE, DELETE, etc.)
        resource_type: Type of resource affected
        resource_id: ID of the resource affected (as string)
        details: Additional details about the action
        user_id: UUID of the user who performed the action
        ip_address: IP address of the user
        user_agent: User agent string

    Returns:
        Created audit log entry
    """
    logger.debug(f"Creating audit log: {action} on {resource_type} by user {user_id}")

    # Serialize details for JSON storage
    serialized_details = serialize_for_json(details) if details else None

    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=serialized_details,
        ip_address=ip_address,
        user_agent=user_agent
    )

    try:
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create audit log: {e}")
        raise

    return audit_log


async def log_action_async(
    db: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    user_id: Optional[uuid.UUID] = None,  # ← UUID
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AuditLog:
    """
    Create an audit log entry asynchronously.

    Args:
        db: Async database session
        action: Action performed
        resource_type: Type of resource affected
        resource_id: ID of the resource
        details: Additional details
        user_id: UUID of the user
        ip_address: Client IP
        user_agent: User agent header

    Returns:
        Created audit log
    """
    logger.debug(f"Creating audit log async: {action} on {resource_type} by user {user_id}")

    serialized_details = serialize_for_json(details) if details else None

    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=serialized_details,
        ip_address=ip_address,
        user_agent=user_agent
    )

    try:
        db.add(audit_log)
        await db.commit()
        await db.refresh(audit_log)
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create async audit log: {e}")
        raise

    return audit_log


def setup_audit_event_listeners():
    """Set up SQLAlchemy event listeners for automatic audit logging (field-level changes only)."""
    from app.models.user import User
    from app.models.department import Department
    from app.models.budget import Budget
    from app.models.transaction import Transaction

    # Map models to resource types
    RESOURCE_TYPES = {
        User: "USER",
        Department: "DEPARTMENT",
        Budget: "BUDGET",
        Transaction: "TRANSACTION"
    }

    def make_listener(model, action):
        def listener(mapper, connection, target):
            session = Session(bind=connection)
            try:
                # Capture field-level changes
                changes = {}
                for attr in mapper.attrs:
                    if attr.key.startswith('_'):
                        continue
                    hist = get_history(target, attr.key)
                    if hist.has_changes():
                        changes[attr.key] = {
                            "old": serialize_for_json(hist.deleted[0]) if hist.deleted else None,
                            "new": serialize_for_json(hist.added[0]) if hist.added else None
                        }

                if not changes:
                    return  # No actual changes

                # Log internal change (no user context)
                log_action(
                    db=session,
                    action=f"{action}_INTERNAL",
                    resource_type=RESOURCE_TYPES[model],
                    resource_id=str(target.id),
                    details={"changed_fields": changes},
                    user_id=None,
                    ip_address=None,
                    user_agent=None
                )
            except Exception as e:
                logger.error(f"Failed to log {action} for {model.__name__}: {e}")
            finally:
                session.close()

        return listener

    # Apply listeners
    for model in [User, Department, Budget, Transaction]:
        event.listen(model, 'after_insert', make_listener(model, "CREATE"))
        event.listen(model, 'after_update', make_listener(model, "UPDATE"))
        event.listen(model, 'after_delete', make_listener(model, "DELETE"))

    logger.info("Audit event listeners setup complete.")