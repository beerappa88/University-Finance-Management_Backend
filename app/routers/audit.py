"""
Audit log endpoints with enhanced RBAC protection.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request, HTTPException, status
from sqlalchemy import select, or_, func, cast, String, desc, outerjoin
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.audit import AuditLog
from app.models.user import User
from app.core.logging import logger
from app.schemas.audit import AuditLogResponse, AuditLogsResponse
from app.utils.pagination import PaginationParams, PaginatedResponse, paginate_query
from app.core.rbac import can_read_audit, can_manage_audit
from app.core.deps import get_pagination_params

router = APIRouter()

@router.get("/", response_model=PaginatedResponse[AuditLogResponse])
async def get_audit_logs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_read_audit),
    pagination: PaginationParams = Depends(get_pagination_params),
    action: Optional[str] = Query(None, description="Filter by action type (CREATE, UPDATE, DELETE, etc.)"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    start_date: Optional[datetime] = Query(None, description="Start date filter (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date filter (ISO format)"),
    search: Optional[str] = Query(None, description="Search in resource ID or details"),
):
    """
    Retrieve audit logs with filtering, search, and pagination.
    """
    logger.info(
        f"User {current_user.id} requesting audit logs | "
        f"Filters: action={action}, resource_type={resource_type}, user_id={user_id}, "
        f"start_date={start_date}, end_date={end_date}, search={search}"
    )
    
    # Base query with join to User table to get username
    stmt = select(AuditLog, User.username).outerjoin(User, AuditLog.user_id == User.id)
    
    # Apply filters
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if start_date:
        stmt = stmt.where(AuditLog.timestamp >= start_date)
    if end_date:
        stmt = stmt.where(AuditLog.timestamp <= end_date)
    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(
            or_(
                AuditLog.resource_id.ilike(search_term),
                cast(AuditLog.details, String).ilike(search_term),
            )
        )
    
    # Create count query for performance
    count_query = select(func.count(AuditLog.id))
    if action:
        count_query = count_query.where(AuditLog.action == action)
    if resource_type:
        count_query = count_query.where(AuditLog.resource_type == resource_type)
    if user_id:
        count_query = count_query.where(AuditLog.user_id == user_id)
    if start_date:
        count_query = count_query.where(AuditLog.timestamp >= start_date)
    if end_date:
        count_query = count_query.where(AuditLog.timestamp <= end_date)
    if search:
        search_term = f"%{search}%"
        count_query = count_query.where(
            or_(
                AuditLog.resource_id.ilike(search_term),
                cast(AuditLog.details, String).ilike(search_term),
            )
        )
    
    # Apply sorting
    if hasattr(AuditLog, pagination.sort_by):
        sort_column = getattr(AuditLog, pagination.sort_by)
        if pagination.sort_order == "desc":
            stmt = stmt.order_by(sort_column.desc())
        else:
            stmt = stmt.order_by(sort_column.asc())
    
    # Apply pagination manually
    offset = (pagination.page - 1) * pagination.size
    paginated_stmt = stmt.offset(offset).limit(pagination.size)
    
    # Execute query
    result = await db.execute(paginated_stmt)
    items = result.all()  # This returns tuples since we selected multiple columns
    
    # Get total count
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    # Calculate pagination metadata
    pages = (total + pagination.size - 1) // pagination.size if total > 0 else 0
    has_next = pagination.page < pages
    has_prev = pagination.page > 1
    
    # Transform items to response format
    transformed_items = []
    for item in items:
        # item is a tuple (AuditLog, username)
        audit_log, username = item
        transformed_items.append(AuditLogResponse(
            id=audit_log.id,
            user_id=audit_log.user_id,
            username=username or "Unknown",  # Use username from joined User table
            action=audit_log.action,
            resource_type=audit_log.resource_type,
            resource_id=audit_log.resource_id,
            details=audit_log.details,
            ip_address=audit_log.ip_address,
            user_agent=audit_log.user_agent,
            timestamp=audit_log.timestamp
        ))
    
    # Create a new PaginatedResponse with the transformed items
    transformed_result = PaginatedResponse(
        items=transformed_items,
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )
    
    # Log access
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    logger.info(
        f"Audit logs accessed by user {current_user.id} from {client_ip} ({user_agent}) | "
        f"Returned {len(transformed_items)} of {total} logs across {pages} pages."
    )
    
    return transformed_result

@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_read_audit),
):
    """
    Retrieve a specific audit log by ID.
    """
    logger.info(f"User {current_user.id} requesting audit log ID: {log_id}")
    
    # Try to parse as integer first, then as UUID
    try:
        # First try to parse as integer
        log_id_int = int(log_id)
        stmt = select(AuditLog, User.username).outerjoin(User, AuditLog.user_id == User.id).where(AuditLog.id == log_id_int)
    except ValueError:
        # If not an integer, try to parse as UUID
        try:
            log_id_uuid = UUID(log_id)
            stmt = select(AuditLog, User.username).outerjoin(User, AuditLog.user_id == User.id).where(AuditLog.id == log_id_uuid)
        except ValueError:
            # If neither, return 422 error
            raise HTTPException(
                status_code=422, 
                detail={
                    "type": "value_error.uuid",
                    "loc": ["path", "log_id"],
                    "msg": "Input should be a valid UUID or integer",
                    "input": log_id
                }
            )
    
    result = await db.execute(stmt)
    log_data = result.first()  # This returns a tuple (AuditLog, username)
    
    if not log_data:
        logger.warning(f"Audit log {log_id} not found (requested by user {current_user.id})")
        raise HTTPException(status_code=404, detail="Audit log not found")
    
    # Unpack the tuple
    audit_log, username = log_data
    
    logger.info(f"Audit log {log_id} accessed by user {current_user.id}")
    return AuditLogResponse(
        id=audit_log.id,
        user_id=audit_log.user_id,
        username=username or "Unknown",
        action=audit_log.action,
        resource_type=audit_log.resource_type,
        resource_id=audit_log.resource_id,
        details=audit_log.details,
        ip_address=audit_log.ip_address,
        user_agent=audit_log.user_agent,
        timestamp=audit_log.timestamp
    )

@router.get("/actions/", response_model=List[str])
async def get_audit_actions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_read_audit),
):
    """
    Get all unique audit actions (e.g., CREATE, UPDATE, DELETE).
    """
    logger.info(f"User {current_user.id} requesting list of audit actions")
    stmt = select(AuditLog.action).distinct()
    result = await db.execute(stmt)
    actions = [row[0] for row in result.all() if row[0]]
    logger.info(f"User {current_user.id} received {len(actions)} unique actions")
    return actions

@router.get("/resource-types/", response_model=List[str])
async def get_audit_resource_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_read_audit),
):
    """
    Get all unique resource types (e.g., USER, BUDGET, DEPARTMENT).
    """
    logger.info(f"User {current_user.id} requesting list of resource types")
    stmt = select(AuditLog.resource_type).distinct()
    result = await db.execute(stmt)
    resource_types = [row[0] for row in result.all() if row[0]]
    logger.info(f"User {current_user.id} received {len(resource_types)} unique resource types")
    return resource_types

@router.get("/stats/")
async def get_audit_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_read_audit),
    days: int = Query(30, ge=1, le=365, description="Number of days to include in stats"),
):
    """
    Get audit statistics over the last N days.
    Includes counts by action, resource type, user, and daily activity.
    """
    logger.info(f"User {current_user.id} requesting audit stats for last {days} days")
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Action counts
    stmt = (
        select(AuditLog.action, func.count(AuditLog.id).label("count"))
        .where(AuditLog.timestamp >= start_date)
        .group_by(AuditLog.action)
    )
    result = await db.execute(stmt)
    action_counts = [{"action": a, "count": c} for a, c in result.all()]
    
    # Resource type counts
    stmt = (
        select(AuditLog.resource_type, func.count(AuditLog.id).label("count"))
        .where(AuditLog.timestamp >= start_date)
        .group_by(AuditLog.resource_type)
    )
    result = await db.execute(stmt)
    resource_type_counts = [{"resource_type": r, "count": c} for r, c in result.all()]
    
    # User activity counts
    stmt = (
        select(AuditLog.user_id, func.count(AuditLog.id).label("count"))
        .where(AuditLog.timestamp >= start_date, AuditLog.user_id.is_not(None))
        .group_by(AuditLog.user_id)
    )
    result = await db.execute(stmt)
    user_counts = [{"user_id": u, "count": c} for u, c in result.all()]
    
    # Daily activity
    stmt = (
        select(func.date(AuditLog.timestamp), func.count(AuditLog.id).label("count"))
        .where(AuditLog.timestamp >= start_date)
        .group_by(func.date(AuditLog.timestamp))
        .order_by(func.date(AuditLog.timestamp))
    )
    result = await db.execute(stmt)
    daily_activity = [{"date": d.isoformat(), "count": c} for d, c in result.all()]
    
    total_logs = sum(item["count"] for item in action_counts)
    stats = {
        "total_logs": total_logs,
        "days": days,
        "action_counts": action_counts,
        "resource_type_counts": resource_type_counts,
        "user_counts": user_counts,
        "daily_activity": daily_activity,
    }
    
    logger.info(f"Stats generated for user {current_user.id}: {total_logs} logs over {days} days")
    return stats

@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audit_log(
    log_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_manage_audit),
):
    """Delete an audit log (requires MANAGE_AUDIT permission)."""
    logger.info(f"Audit log deletion requested for ID: {log_id} by user {current_user.id}")
    
    try:
        log_id_uuid = UUID(log_id)
        result = await db.execute(select(AuditLog).where(AuditLog.id == log_id_uuid))
        log = result.scalar_one_or_none()
        
        if not log:
            logger.warning(f"Audit log {log_id} not found for deletion (requested by user {current_user.id})")
            raise HTTPException(status_code=404, detail="Audit log not found")
        
        await db.delete(log)
        await db.commit()
        
        logger.info(f"Audit log {log_id} deleted by user {current_user.id}")
    except ValueError:
        raise HTTPException(
            status_code=422, 
            detail={
                "type": "value_error.uuid",
                "loc": ["path", "log_id"],
                "msg": "Input should be a valid UUID",
                "input": log_id
            }
        )
