"""
Department API endpoints.
This module provides CRUD endpoints for departments.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import logger
from app.core.deps import (
    get_request_client,
    can_create_department, 
    can_read_department
)
from app.core.deps import get_pagination_params
from app.core.rbac import (
    get_department_with_access, update_department_with_access, delete_department_with_access
)
from app.db.session import get_db
from app.schemas.department import (
    Department,
    DepartmentCreate,
    DepartmentUpdate,
)
from app.services.department import DepartmentService
from app.utils.pagination import PaginationParams, paginate_query, PaginatedResponse
from uuid import UUID
from sqlalchemy import select, func
from app.models.department import Department as DepartmentModel

router = APIRouter()

@router.post("/", response_model=Department, status_code=status.HTTP_201_CREATED)
async def create_department(
    department_in: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(can_create_department),
    client_info = Depends(get_request_client)
) -> Department:
    """
    Create a new department.
    
    Args:
        department_in: Department creation data
        db: Database session
        current_user: Current authenticated user
        client_info: Client IP and user agent
        
    Returns:
        Created department
    """
    logger.info(f"Department creation requested by: {current_user.username}")
    
    existing_department = await DepartmentService.get_by_code(db, department_in.code)
    if existing_department:
        logger.warning(f"Department code already exists: {department_in.code}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department code already exists",
        )
    
    department = await DepartmentService.create(
        db, 
        department_in, 
        user_id=current_user.id,
        ip_address=client_info["ip_address"],
        user_agent=client_info["user_agent"]
    )
    
    logger.info(f"Department created successfully: {department.id}")
    return department

@router.get("/{department_id}", response_model=Department)
async def get_department(
    department: DepartmentModel = Depends(get_department_with_access)
) -> Department:
    """
    Get a department by ID.
    
    Args:
        department_id: Department ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Department details
    """
    logger.info(f"Department details requested for ID: {department.id}")
    return department

@router.get("/", response_model=PaginatedResponse[Department])
async def get_all_departments(
    db: AsyncSession = Depends(get_db),
    pagination: PaginationParams = Depends(get_pagination_params),
    current_user = Depends(can_read_department)
):
    """
    Get all departments with pagination, search, and sorting.
    """
    try:
        # Build base query
        query = select(DepartmentModel)
        
        # Apply search filter if provided
        if pagination.search:
            search_term = f"%{pagination.search}%"
            query = query.where(
                DepartmentModel.name.ilike(search_term) | 
                DepartmentModel.code.ilike(search_term)
            )
        
        # Create count query for performance
        count_query = select(func.count(DepartmentModel.id))
        if pagination.search:
            search_term = f"%{pagination.search}%"
            count_query = count_query.where(
                DepartmentModel.name.ilike(search_term) | 
                DepartmentModel.code.ilike(search_term)
            )
        
        # Execute paginated query
        result = await paginate_query(db, query, pagination, count_query, DepartmentModel)
        
        logger.info(f"Retrieved {len(result.items)} departments (page {result.page} of {result.pages})")
        
        return result
    except Exception as e:
        logger.error(f"Error fetching departments: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch departments: {str(e)}"
        )

@router.put("/{department_id}", response_model=Department)
async def update_department(
    department_id: UUID,
    department_in: DepartmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(update_department_with_access),
    client_info = Depends(get_request_client)
) -> Department:
    """
    Update a department.
    
    Args:
        department_id: Department ID
        department_in: Department update data
        db: Database session
        current_user: Current authenticated user
        client_info: Client IP and user agent
        
    Returns:
        Updated department
    """
    logger.info(f"Department update requested for ID: {department_id} by: {current_user.username}")
    
    department = await DepartmentService.get_by_id(db, department_id)
    if not department:
        logger.warning(f"Department not found for update: {department_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )
    
    if department_in.code and department_in.code != department.code:
        existing_department = await DepartmentService.get_by_code(db, department_in.code)
        if existing_department:
            logger.warning(f"Department code already exists: {department_in.code}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department code already exists",
            )
    
    updated_department = await DepartmentService.update(
        db, 
        department_id, 
        department_in,
        user_id=current_user.id,
        ip_address=client_info["ip_address"],
        user_agent=client_info["user_agent"]
    )
    
    logger.info(f"Department updated successfully: {department_id}")
    return updated_department

@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(delete_department_with_access),
    client_info = Depends(get_request_client)
) -> None:
    """
    Delete a department.
    
    Args:
        department_id: Department ID
        db: Database session
        current_user: Current authenticated user
        client_info: Client IP and user agent
    """
    logger.info(f"Department deletion requested for ID: {department_id} by: {current_user.username}")
    
    success = await DepartmentService.delete(
        db, 
        department_id,
        user_id=current_user.id,
        ip_address=client_info["ip_address"],
        user_agent=client_info["user_agent"]
    )
    
    if not success:
        logger.warning(f"Department not found for deletion: {department_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )
    
    logger.info(f"Department deleted successfully: {department_id}")
