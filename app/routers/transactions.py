"""
Transaction API endpoints.
This module provides CRUD endpoints for transactions.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import logger
from app.core.deps import (
    get_request_client,
    can_create_transaction, can_read_transaction
)
from app.core.rbac import (
    get_transaction_with_access, update_transaction_with_access, delete_transaction_with_access
)
from app.db.session import get_db
from app.core.auth import get_current_active_user
from app.schemas.transaction import (
    Transaction,
    TransactionCreate,
    TransactionUpdate,
)
from app.services.transaction import TransactionService
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
    transaction: Transaction = Depends(get_transaction_with_access)
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

@router.get("/", response_model=List[Transaction])
async def get_all_transactions(
    skip: int = 0,
    limit: int = 100,
    budget_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(can_read_transaction)
) -> List[Transaction]:
    """
    Get all transactions with optional filtering by budget.
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        budget_id: Optional budget ID to filter by
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of transactions
    """
    logger.info(f"Transaction list requested by: {current_user.username}")
    
    if budget_id:
        transactions = await TransactionService.get_by_budget(
            db, budget_id, skip=skip, limit=limit
        )
    else:
        transactions = await TransactionService.get_all(db, skip=skip, limit=limit)
    
    logger.info(f"Retrieved {len(transactions)} transactions")
    return transactions

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
