"""
Service layer for transaction operations.

This module contains the business logic for transaction-related operations,
abstracting away the database operations from the API endpoints.
"""

from typing import List, Optional
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.logging import logger
from app.models.transaction import Transaction, TransactionType
from app.schemas.transaction import TransactionCreate, TransactionUpdate
from app.db.audit import log_action_async
from .budget import BudgetService
from uuid import UUID


class TransactionService:
    """Service class for transaction operations."""
    
    @staticmethod
    async def create(
        db: AsyncSession,
        transaction_in: TransactionCreate,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Transaction:
        """
        Create a new transaction.

        Args:
            db: Database session
            transaction_in: Transaction creation data
            user_id: ID of the user performing the action
            ip_address: IP address of the user
            user_agent: User agent string

        Returns:
            Created transaction
        """
        logger.info(
            f"Creating new {transaction_in.transaction_type.value} transaction "
            f"for budget: {transaction_in.budget_id}"
        )

        # Get the budget to check existence and funds
        budget = await BudgetService.get_by_id(db, transaction_in.budget_id)
        if not budget:
            logger.error(f"Budget not found, ID: {transaction_in.budget_id}")
            raise ValueError(f"Budget not found, ID: {transaction_in.budget_id}")

        # Validate sufficient funds for expense or transfer out
        if transaction_in.transaction_type in [TransactionType.EXPENSE, TransactionType.TRANSFER_OUT]:
            if budget.remaining_amount < transaction_in.amount:
                logger.error(
                    f"Insufficient funds in budget {budget.id}. "
                    f"Required: {transaction_in.amount}, Available: {budget.remaining_amount}"
                )
                raise ValueError("Insufficient funds in budget")

        # Create transaction
        transaction = Transaction(**transaction_in.model_dump())  # Use model_dump() for Pydantic v2
        db.add(transaction)

        # Commit and refresh to get DB-generated fields (like ID)
        await db.commit()
        await db.refresh(transaction)

        # 🔐 Eagerly extract values before any potential session expiration
        transaction_id = transaction.id
        budget_id = transaction.budget_id
        amount = transaction.amount
        description = transaction.description
        reference_number = transaction.reference_number
        transaction_type = transaction.transaction_type.value

        # Update the budget's spent amount
        amount_change = Decimal("0.00")
        if transaction_in.transaction_type == TransactionType.EXPENSE:
            amount_change = transaction_in.amount
        elif transaction_in.transaction_type == TransactionType.REFUND:
            amount_change = -transaction_in.amount
        elif transaction_in.transaction_type == TransactionType.TRANSFER_OUT:
            amount_change = transaction_in.amount
        elif transaction_in.transaction_type == TransactionType.TRANSFER_IN:
            amount_change = -transaction_in.amount

        await BudgetService.update_spent_amount(
            db,
            budget_id=budget.id,
            amount_change=amount_change,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Log the creation action using only primitive/eager values
        await log_action_async(
            db,
            action="CREATE",
            resource_type="TRANSACTION",
            resource_id=str(transaction_id),
            details={
                "budget_id": str(budget_id),
                "transaction_type": transaction_type,
                "amount": str(amount),
                "description": description or "",
                "reference_number": reference_number or ""
            },
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        logger.info(f"Created transaction with ID: {transaction_id}")
        return transaction
    
    @staticmethod
    async def get_by_id(
        db: AsyncSession, 
        transaction_id: UUID
    ) -> Optional[Transaction]:
        """
        Get a transaction by ID.
        
        Args:
            db: Database session
            transaction_id: Transaction ID
            
        Returns:
            Transaction if found, None otherwise
        """
        logger.debug(f"Getting transaction by ID: {transaction_id}")
        
        result = await db.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        return result.scalars().first()
    
    @staticmethod
    async def get_by_reference_number(
        db: AsyncSession, 
        reference_number: str
    ) -> Optional[Transaction]:
        """
        Get a transaction by reference number.
        
        Args:
            db: Database session
            reference_number: Transaction reference number
            
        Returns:
            Transaction if found, None otherwise
        """
        logger.debug(f"Getting transaction by reference number: {reference_number}")
        
        result = await db.execute(
            select(Transaction).where(Transaction.reference_number == reference_number)
        )
        return result.scalars().first()
    
    @staticmethod
    async def get_all(
        db: AsyncSession, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Transaction]:
        """
        Get all transactions with pagination.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of transactions
        """
        logger.debug(f"Getting all transactions, skip={skip}, limit={limit}")
        
        result = await db.execute(
            select(Transaction).offset(skip).limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_by_budget(
        db: AsyncSession, 
        budget_id: UUID,
        skip: int = 0, 
        limit: int = 100
    ) -> List[Transaction]:
        """
        Get all transactions for a specific budget.
        
        Args:
            db: Database session
            budget_id: Budget ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of transactions for the budget
        """
        logger.debug(
            f"Getting transactions for budget {budget_id}, "
            f"skip={skip}, limit={limit}"
        )
        
        result = await db.execute(
            select(Transaction)
            .where(Transaction.budget_id == budget_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def update(
        db: AsyncSession, 
        transaction_id: UUID, 
        transaction_in: TransactionUpdate,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[Transaction]:
        """
        Update a transaction.
        
        Args:
            db: Database session
            transaction_id: Transaction ID
            transaction_in: Transaction update data
            user_id: ID of the user performing the action
            ip_address: IP address of the user
            user_agent: User agent string
            
        Returns:
            Updated transaction if found, None otherwise
        """
        logger.info(f"Updating transaction with ID: {transaction_id}")
        
        # Check if transaction exists
        transaction = await TransactionService.get_by_id(db, transaction_id)
        if not transaction:
            logger.warning(
                f"Transaction not found for update, ID: {transaction_id}"
            )
            return None
        
        # Get the budget
        budget = await BudgetService.get_by_id(db, transaction.budget_id)
        if not budget:
            logger.error(
                f"Budget not found for transaction update, "
                f"budget ID: {transaction.budget_id}"
            )
            return None
        
        # Store the old amount for budget adjustment
        old_amount = transaction.amount
        
        # Update the transaction
        update_data = transaction_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(transaction, field, value)
        
        await db.commit()
        await db.refresh(transaction)
        
        # If the amount changed, update the budget's spent amount
        if "amount" in update_data:
            new_amount = transaction.amount
            amount_diff = new_amount - old_amount
            
            # Determine the sign of the adjustment based on transaction type
            if transaction.transaction_type in [TransactionType.EXPENSE, TransactionType.TRANSFER_OUT]:
                # For expenses and transfers out, more amount means more spent
                await BudgetService.update_spent_amount(
                    db, budget.id, amount_diff,
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
            elif transaction.transaction_type in [TransactionType.REFUND, TransactionType.TRANSFER_IN]:
                # For refunds and transfers in, more amount means less spent
                await BudgetService.update_spent_amount(
                    db, budget.id, -amount_diff,
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
        
        # Log the action
        changes = {}
        for field in update_data:
            changes[field] = {
                "old": str(getattr(transaction, field)),
                "new": str(update_data[field])
            }
        
        await log_action_async(
            db,
            action="UPDATE",
            resource_type="TRANSACTION",
            resource_id=str(transaction.id),
            details=changes,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        logger.info(f"Updated transaction ID: {transaction.id}")
        return transaction
    
    @staticmethod
    async def delete(
        db: AsyncSession, 
        transaction_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Delete a transaction.
        
        Args:
            db: Database session
            transaction_id: Transaction ID
            user_id: ID of the user performing the action
            ip_address: IP address of the user
            user_agent: User agent string
            
        Returns:
            True if transaction was deleted, False otherwise
        """
        logger.info(f"Deleting transaction with ID: {transaction_id}")
        
        transaction = await TransactionService.get_by_id(db, transaction_id)
        if not transaction:
            logger.warning(
                f"Transaction not found for deletion, ID: {transaction_id}"
            )
            return False
        
        # Get the budget
        budget = await BudgetService.get_by_id(db, transaction.budget_id)
        if not budget:
            logger.error(
                f"Budget not found for transaction deletion, "
                f"budget ID: {transaction.budget_id}"
            )
            return False
        
        # Determine the amount to adjust the budget by
        amount_adjustment = Decimal("0.00")
        
        if transaction.transaction_type in [TransactionType.EXPENSE, TransactionType.TRANSFER_OUT]:
            # For expenses and transfers out, deletion means less spent
            amount_adjustment = -transaction.amount
        elif transaction.transaction_type in [TransactionType.REFUND, TransactionType.TRANSFER_IN]:
            # For refunds and transfers in, deletion means more spent
            amount_adjustment = transaction.amount
        
        # Store values for audit log
        transaction_values = {
            "id": transaction.id,
            "budget_id": transaction.budget_id,
            "transaction_type": transaction.transaction_type.value,
            "amount": str(transaction.amount),
            "description": transaction.description,
            "reference_number": transaction.reference_number
        }
        
        # Delete the transaction
        await db.delete(transaction)
        await db.commit()
        
        # Update the budget's spent amount
        await BudgetService.update_spent_amount(
            db, budget.id, amount_adjustment,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Log the action
        await log_action_async(
            db,
            action="DELETE",
            resource_type="TRANSACTION",
            resource_id=str(transaction.id),
            details=transaction_values,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        logger.info(f"Deleted transaction ID: {transaction_id}")
        return True