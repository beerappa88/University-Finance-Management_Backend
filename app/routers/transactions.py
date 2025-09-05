"""
Transaction API endpoints.
This module provides CRUD endpoints for transactions.
"""
from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.logging import logger
from app.core.deps import (
    get_request_client,
    can_create_transaction, can_read_transaction
)
from app.core.deps import get_pagination_params
from app.core.rbac import (
    get_transaction_with_access, update_transaction_with_access, delete_transaction_with_access
)
from app.db.session import get_db
from app.core.auth import get_current_active_user
from app.schemas.transaction import (
    Transaction,
    TransactionCreate,
    TransactionUpdate,
    TransactionWithDetails,
)
from app.services.transaction import TransactionService
from app.utils.pagination import PaginationParams, PaginatedResponse, paginate_query
from datetime import datetime
from app.models.transaction import Transaction as TransactionModel
from app.models.budget import Budget
from app.models.department import Department
from uuid import UUID
router = APIRouter()

@router.post("/", response_model=Transaction, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    transaction_in: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(can_create_transaction),
    client_info = Depends(get_request_client)
) -> Transaction:
    """
    Create a new transaction.
    
    Args:
        transaction_in: Transaction creation data
        db: Database session
        current_user: Current authenticated user
        client_info: Client IP and user agent
        
    Returns:
        Created transaction
    """
    logger.info(f"Transaction creation requested by: {current_user.username}")
    
    try:
        transaction = await TransactionService.create(
            db, 
            transaction_in,
            user_id=current_user.id,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"]
        )
        logger.info(f"Transaction created successfully: {transaction.id}")
        return transaction
    except ValueError as e:
        logger.warning(f"Transaction creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

@router.get("/{transaction_id}", response_model=Transaction)
async def get_transaction(
    transaction: TransactionModel = Depends(get_transaction_with_access)
) -> Transaction:
    """
    Get a transaction by ID.
    
    Args:
        transaction_id: Transaction ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Transaction
    """
    logger.info(f"Transaction details requested for ID: {transaction.id}")
    return transaction

@router.get("/", response_model=PaginatedResponse[TransactionWithDetails])
async def get_all_transactions(
    db: AsyncSession = Depends(get_db),
    pagination: PaginationParams = Depends(get_pagination_params),
    budget_id: Optional[UUID] = Query(None, description="Filter by budget ID"),
    department_id: Optional[UUID] = Query(None, description="Filter by department ID"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type"),
    current_user = Depends(can_read_transaction)
) -> PaginatedResponse[TransactionWithDetails]:
    """
    Get all transactions with optional filters and pagination.
    Args:
        db: Database session
        pagination: Pagination parameters
        budget_id: Optional budget ID to filter by
        department_id: Optional department ID to filter by
        start_date: Optional start date to filter by
        end_date: Optional end date to filter by
        transaction_type: Optional transaction type to filter by
        current_user: Current authenticated user
        
        Returns:
        Paginated list of transactions with details
    """
    try:
        # Define allowed sort fields
        sort_fields = {
            "id": TransactionModel.id,
            "transaction_date": TransactionModel.transaction_date,
            "amount": TransactionModel.amount,
            "created_at": TransactionModel.created_at,
            "updated_at": TransactionModel.updated_at,
            "department_name": Department.name,
        }
        
        # Base query with joins and labels
        query = (
            select(
                TransactionModel.id,
                TransactionModel.budget_id,
                TransactionModel.transaction_type,
                TransactionModel.amount,
                TransactionModel.description,
                TransactionModel.reference_number,
                TransactionModel.transaction_date,
                TransactionModel.created_at,
                TransactionModel.updated_at,
                Department.name.label("department_name"),
                Budget.fiscal_year.label("fiscal_year"),
            )
            .join(Budget, TransactionModel.budget_id == Budget.id)
            .join(Department, Budget.department_id == Department.id)
        )
        
        # Apply filters
        if budget_id:
            query = query.where(TransactionModel.budget_id == budget_id)
        if department_id:
            query = query.where(Department.id == department_id)
        if start_date:
            query = query.where(TransactionModel.transaction_date >= start_date)
        if end_date:
            query = query.where(TransactionModel.transaction_date <= end_date)
        if transaction_type:
            query = query.where(TransactionModel.transaction_type == transaction_type)
        if pagination.search:
            term = f"%{pagination.search}%"
            query = query.where(
                TransactionModel.description.ilike(term) |
                Department.name.ilike(term) |
                Budget.fiscal_year.ilike(term)
            )
        
        # Sorting
        sort_col = sort_fields.get(pagination.sort_by)
        if sort_col is not None:
            query = query.order_by(
                sort_col.desc() if pagination.sort_order == "desc" else sort_col.asc()
            )
        else:
            query = query.order_by(TransactionModel.transaction_date.desc())
        
        # Count query (same joins)
        count_query = (
            select(func.count(TransactionModel.id))
            .join(Budget, TransactionModel.budget_id == Budget.id)
            .join(Department, Budget.department_id == Department.id)
        )
        
        # Apply same filters to count query
        for criterion in query._where_criteria:
            count_query = count_query.where(criterion)
        
        # Use paginate_query with use_scalars=False
        paginated_result = await paginate_query(
            db=db,
            query=query,
            count_query=count_query,
            pagination=pagination,
            model=None,
            use_scalars=False  # Critical: we're returning Row objects
        )
        
        # Transform Row objects to dicts
        transformed_items = []
        for row in paginated_result.items:
            if not hasattr(row, '_mapping'):
                continue
            item_dict = {
                key: str(value) if isinstance(value, UUID)
                else float(value) if isinstance(value, Decimal)
                else value.isoformat() if isinstance(value, datetime)
                else value
                for key, value in row._mapping.items()
            }
            # Add computed field
            item_dict["budget_name"] = f"{item_dict.get('department_name', 'Unknown')} - {item_dict.get('fiscal_year', 'Unknown')}"
            transformed_items.append(item_dict)
        
        # Create a new PaginatedResponse with transformed items and pagination metadata
        return PaginatedResponse[TransactionWithDetails](
            items=transformed_items,
            total=paginated_result.total,
            page=paginated_result.page,
            size=paginated_result.size,
            pages=paginated_result.pages,
            has_next=paginated_result.has_next,
            has_prev=paginated_result.has_prev,
            next_page=paginated_result.next_page,
            prev_page=paginated_result.prev_page
        )
    except Exception as e:
        logger.error(f"Error fetching transactions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch transactions: {str(e)}"
        )

@router.put("/{transaction_id}", response_model=Transaction)
async def update_transaction(
    transaction_id: UUID,
    transaction_in: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(update_transaction_with_access),
    client_info = Depends(get_request_client)
) -> Transaction:
    """
    Update a transaction.
    
    Args:
        transaction_id: Transaction ID
        transaction_in: Transaction update data
        db: Database session
        current_user: Current authenticated user
        client_info: Client IP and user agent
        
    Returns:
        Updated transaction
    """
    logger.info(f"Transaction update requested for ID: {transaction_id} by: {current_user.username}")
    
    transaction = await TransactionService.get_by_id(db, transaction_id)
    if not transaction:
        logger.warning(f"Transaction not found for update: {transaction_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    
    updated_transaction = await TransactionService.update(
        db, 
        transaction_id, 
        transaction_in,
        user_id=current_user.id,
        ip_address=client_info["ip_address"],
        user_agent=client_info["user_agent"]
    )
    
    logger.info(f"Transaction updated successfully: {transaction_id}")
    return updated_transaction

@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(delete_transaction_with_access),
    client_info = Depends(get_request_client)
) -> None:
    """
    Delete a transaction.
    
    Args:
        transaction_id: Transaction ID
        db: Database session
        current_user: Current authenticated user
        client_info: Client IP and user agent
    """
    logger.info(f"Transaction deletion requested for ID: {transaction_id} by: {current_user.username}")
    
    success = await TransactionService.delete(
        db, 
        transaction_id,
        user_id=current_user.id,
        ip_address=client_info["ip_address"],
        user_agent=client_info["user_agent"]
    )
    
    if not success:
        logger.warning(f"Transaction not found for deletion: {transaction_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    
    logger.info(f"Transaction deleted successfully: {transaction_id}")
