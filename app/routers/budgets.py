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
from app.core.deps import get_pagination_params
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
    BudgetWithDetails,
)
from app.services.budget import BudgetService
from app.utils.pagination import PaginationParams, paginate_query, PaginatedResponse
from uuid import UUID
from sqlalchemy import func

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

@router.get("/", response_model=PaginatedResponse[BudgetWithDetails])
async def get_all_budgets(
    db: AsyncSession = Depends(get_db),
    pagination: PaginationParams = Depends(get_pagination_params),
    department_id: Optional[UUID] = Query(None, description="Filter by department ID"),
    fiscal_year: Optional[int] = Query(None, description="Filter by fiscal year"),
    current_user = Depends(can_read_budget)
):
    """
    Get all budgets with pagination, search, sorting, and filtering.
    """
    try:
        # Build base query with joins for related data
        query = (
            select(BudgetModel, Department.name.label("department_name"))
            .join(Department, BudgetModel.department_id == Department.id, isouter=True)
        )
        
        # Apply filters
        if department_id:
            query = query.where(BudgetModel.department_id == department_id)
        
        if fiscal_year:
            query = query.where(BudgetModel.fiscal_year == fiscal_year)
        
        # Apply search if provided
        if pagination.search:
            search_term = f"%{pagination.search}%"
            query = query.where(
                BudgetModel.name.ilike(search_term) | 
                Department.name.ilike(search_term)
            )
        
        # Create count query
        count_query = select(func.count(BudgetModel.id))
        if department_id:
            count_query = count_query.where(BudgetModel.department_id == department_id)
        if fiscal_year:
            count_query = count_query.where(BudgetModel.fiscal_year == fiscal_year)
        if pagination.search:
            search_term = f"%{pagination.search}%"
            count_query = count_query.where(
                BudgetModel.name.ilike(search_term) | 
                Department.name.ilike(search_term)
            )
        
        # Execute paginated query
        result = await paginate_query(db, query, pagination, count_query, BudgetModel)
        
        # Transform results to include department name
        transformed_items = []
        for item in result.items:
            # Handle different possible result formats
            if hasattr(item, '_mapping'):
                # For Row objects
                try:
                    # Try to access by model name and column label
                    budget_model = item.BudgetModel
                    department_name = item.department_name
                except AttributeError:
                    try:
                        # Try to access by index
                        budget_model = item[0]
                        department_name = item[1]
                    except (IndexError, TypeError):
                        # If that fails, check if item itself is the BudgetModel
                        if hasattr(item, 'id') and hasattr(item, 'department_id'):
                            # The item itself is the BudgetModel
                            budget_model = item
                            department_name = getattr(item, 'department_name', None)
                        else:
                            raise ValueError("Unable to extract BudgetModel and department_name from query result")
                
                # Handle None department_name
                if department_name is None:
                    department_name = "Unknown Department"
                
                # Create BudgetWithDetails object
                budget_with_details = BudgetWithDetails(
                    id=str(budget_model.id),
                    department_id=str(budget_model.department_id),
                    fiscal_year=budget_model.fiscal_year,
                    total_amount=float(budget_model.total_amount),
                    description=budget_model.description,
                    spent_amount=float(budget_model.spent_amount),
                    remaining_amount=float(budget_model.remaining_amount),
                    department_name=department_name,  # Now guaranteed to be a string
                    created_at=budget_model.created_at,
                    updated_at=budget_model.updated_at
                )
            elif isinstance(item, dict):
                # For dictionary results
                department_name = item.get("department_name") or "Unknown Department"
                
                budget_with_details = BudgetWithDetails(
                    id=str(item["id"]),
                    department_id=str(item["department_id"]),
                    fiscal_year=item["fiscal_year"],
                    total_amount=float(item["total_amount"]),
                    description=item["description"],
                    spent_amount=float(item["spent_amount"]),
                    remaining_amount=float(item["remaining_amount"]),
                    department_name=department_name,  # Now guaranteed to be a string
                    created_at=item["created_at"],
                    updated_at=item["updated_at"]
                )
            elif hasattr(item, 'id') and hasattr(item, 'department_id'):
                # For Budget objects
                department_name = getattr(item, 'department_name', None) or "Unknown Department"
                
                budget_with_details = BudgetWithDetails(
                    id=str(item.id),
                    department_id=str(item.department_id),
                    fiscal_year=item.fiscal_year,
                    total_amount=float(item.total_amount),
                    description=item.description,
                    spent_amount=float(item.spent_amount),
                    remaining_amount=float(item.remaining_amount),
                    department_name=department_name,  # Now guaranteed to be a string
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
            else:
                # For other types of results
                raise ValueError(f"Unexpected result type: {type(item)}")
            
            transformed_items.append(budget_with_details)
        
        # Create a new PaginatedResponse with the transformed items
        transformed_result = PaginatedResponse(
            items=transformed_items,
            total=result.total,
            page=result.page,
            size=result.size,
            pages=result.pages,
            has_next=result.has_next,
            has_prev=result.has_prev
        )
        
        logger.info(f"Retrieved {len(transformed_items)} budgets (page {transformed_result.page} of {transformed_result.pages})")
        
        return transformed_result
    except Exception as e:
        logger.error(f"Error fetching budgets: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch budgets: {str(e)}"
        )

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
