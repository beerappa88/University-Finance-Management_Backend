"""
Budget API endpoints.
This module provides CRUD endpoints for budgets.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.logging import logger
from app.core.deps import (
    get_request_client,
    can_create_budget, can_read_budget
)
from app.core.rbac import (
    get_budget_with_access, update_budget_with_access, delete_budget_with_access
)
from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.budget import Budget as BudgetModel
from app.models.department import Department
from app.schemas.budget import (
    Budget,
    BudgetCreate,
    BudgetUpdate,
)
from app.services.budget import BudgetService
from uuid import UUID
router = APIRouter()

@router.post("/", response_model=Budget, status_code=status.HTTP_201_CREATED)
async def create_budget(
    budget_in: BudgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(can_create_budget),
    client_info = Depends(get_request_client)
) -> Budget:
    """
    Create a new budget.
    
    Args:
        budget_in: Budget creation data
        db: Database session
        current_user: Current authenticated user
        client_info: Client IP and user agent
        
    Returns:
        Created budget
    """
    logger.info(f"Budget creation requested by: {current_user.username}")
    
    try:
        budget = await BudgetService.create(
            db, 
            budget_in,
            user_id=current_user.id,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"]
        )
        logger.info(f"Budget created successfully: {budget.id}")
        return budget
    except ValueError as e:
        logger.warning(f"Budget creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

@router.get("/{budget_id}", response_model=Budget)
async def get_budget(
    budget: Budget = Depends(get_budget_with_access)
) -> Budget:
    """
    Get a budget by ID.
    
    Args:
        budget_id: Budget ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Budget
    """
    logger.info(f"Budget details requested for ID: {budget.id}")
    return budget

@router.get("/", response_model=List[Budget])
async def get_all_budgets(
    skip: int = 0,
    limit: int = 100,
    department_id: Optional[UUID] = Query(None, description="Filter by department ID"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(can_read_budget)
) -> List[Budget]:
    """
    Get all budgets with optional filtering by department.
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        department_id: Optional department ID to filter by
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of budgets
    """
    logger.info(f"Budget list requested by: {current_user.username}")
    
    if department_id:
        budgets = await BudgetService.get_by_department(
            db, department_id, skip=skip, limit=limit
        )
    else:
        budgets = await BudgetService.get_all(db, skip=skip, limit=limit)
    
    logger.info(f"Retrieved {len(budgets)} budgets")
    return budgets

@router.put("/{budget_id}", response_model=Budget)
async def update_budget(
    budget_id: UUID,
    budget_in: BudgetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(update_budget_with_access),
    client_info = Depends(get_request_client)
) -> Budget:
    """
    Update a budget.
    
    Args:
        budget_id: Budget ID
        budget_in: Budget update data
        db: Database session
        current_user: Current authenticated user
        client_info: Client IP and user agent
        
    Returns:
        Updated budget
    """
    logger.info(f"Budget update requested for ID: {budget_id} by: {current_user.username}")
    
    budget = await BudgetService.get_by_id(db, budget_id)
    if not budget:
        logger.warning(f"Budget not found for update: {budget_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found",
        )
    
    updated_budget = await BudgetService.update(
        db, 
        budget_id, 
        budget_in,
        user_id=current_user.id,
        ip_address=client_info["ip_address"],
        user_agent=client_info["user_agent"]
    )
    
    logger.info(f"Budget updated successfully: {budget_id}")
    return updated_budget

@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    budget_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(delete_budget_with_access),
    client_info = Depends(get_request_client)
) -> None:
    """
    Delete a budget.
    
    Args:
        budget_id: Budget ID
        db: Database session
        current_user: Current authenticated user
        client_info: Client IP and user agent
    """
    logger.info(f"Budget deletion requested for ID: {budget_id} by: {current_user.username}")
    
    success = await BudgetService.delete(
        db, 
        budget_id,
        user_id=current_user.id,
        ip_address=client_info["ip_address"],
        user_agent=client_info["user_agent"]
    )
    
    if not success:
        logger.warning(f"Budget not found for deletion: {budget_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found",
        )
    
    logger.info(f"Budget deleted successfully: {budget_id}")
