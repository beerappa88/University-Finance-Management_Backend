"""
Service layer for budget operations.

This module contains the business logic for budget-related operations,
abstracting away the database operations from the API endpoints.
"""

from typing import List, Optional
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.core.logging import logger
from app.models.budget import Budget
from app.schemas.budget import BudgetCreate, BudgetUpdate
from app.db.audit import log_action_async
from uuid import UUID


class BudgetService:
    """Service class for budget operations."""
    
    @staticmethod
    async def create(
        db: AsyncSession, 
        budget_in: BudgetCreate,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Budget:
        """
        Create a new budget.
        
        Args:
            db: Database session
            budget_in: Budget creation data
            user_id: ID of the user performing the action
            ip_address: IP address of the user
            user_agent: User agent string
            
        Returns:
            Created budget
        """
        logger.info(
            f"Creating new budget for department: {budget_in.department_id}"
        )
        
        # Check if a budget already exists for this department and fiscal year
        existing_budget = await BudgetService.get_by_department_and_fiscal_year(
            db, budget_in.department_id, budget_in.fiscal_year
        )
        
        if existing_budget:
            logger.warning(
                f"Budget already exists for department {budget_in.department_id} "
                f"in fiscal year {budget_in.fiscal_year}"
            )
            raise ValueError(
                f"Budget already exists for department {budget_in.department_id} "
                f"in fiscal year {budget_in.fiscal_year}"
            )
        
        # Create the budget with remaining amount equal to total amount
        budget_data = budget_in.dict()
        budget_data["remaining_amount"] = budget_data["total_amount"]
        budget = Budget(**budget_data)
        
        db.add(budget)
        await db.commit()
        await db.refresh(budget)
        
        # Log the action
        await log_action_async(
            db,
            action="CREATE",
            resource_type="BUDGET",
            resource_id=str(budget.id),
            details={
                "department_id": budget.department_id,
                "fiscal_year": budget.fiscal_year,
                "total_amount": str(budget.total_amount)
            },
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        logger.info(f"Created budget with ID: {budget.id}")
        return budget
    
    @staticmethod
    async def get_by_id(
        db: AsyncSession, 
        budget_id: UUID
    ) -> Optional[Budget]:
        """
        Get a budget by ID.
        
        Args:
            db: Database session
            budget_id: Budget ID
            
        Returns:
            Budget if found, None otherwise
        """
        logger.debug(f"Getting budget by ID: {budget_id}")
        
        result = await db.execute(
            select(Budget).where(Budget.id == budget_id)
        )
        return result.scalars().first()
    
    @staticmethod
    async def get_by_department_and_fiscal_year(
        db: AsyncSession, 
        department_id: UUID, 
        fiscal_year: str
    ) -> Optional[Budget]:
        """
        Get a budget by department ID and fiscal year.
        
        Args:
            db: Database session
            department_id: Department ID
            fiscal_year: Fiscal year
            
        Returns:
            Budget if found, None otherwise
        """
        logger.debug(
            f"Getting budget for department {department_id} "
            f"in fiscal year {fiscal_year}"
        )
        
        result = await db.execute(
            select(Budget).where(
                and_(
                    Budget.department_id == department_id,
                    Budget.fiscal_year == fiscal_year
                )
            )
        )
        return result.scalars().first()
    
    @staticmethod
    async def get_all(
        db: AsyncSession, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Budget]:
        """
        Get all budgets with pagination.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of budgets
        """
        logger.debug(f"Getting all budgets, skip={skip}, limit={limit}")
        
        result = await db.execute(
            select(Budget).offset(skip).limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_by_department(
        db: AsyncSession, 
        department_id: UUID,
        skip: int = 0, 
        limit: int = 100
    ) -> List[Budget]:
        """
        Get all budgets for a specific department.
        
        Args:
            db: Database session
            department_id: Department ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of budgets for the department
        """
        logger.debug(
            f"Getting budgets for department {department_id}, "
            f"skip={skip}, limit={limit}"
        )
        
        result = await db.execute(
            select(Budget)
            .where(Budget.department_id == department_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def update(
        db: AsyncSession, 
        budget_id: UUID, 
        budget_in: BudgetUpdate,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[Budget]:
        """
        Update a budget.
        
        Args:
            db: Database session
            budget_id: Budget ID
            budget_in: Budget update data
            user_id: ID of the user performing the action
            ip_address: IP address of the user
            user_agent: User agent string
            
        Returns:
            Updated budget if found, None otherwise
        """
        logger.info(f"Updating budget with ID: {budget_id}")
        
        budget = await BudgetService.get_by_id(db, budget_id)
        if not budget:
            logger.warning(f"Budget not found for update, ID: {budget_id}")
            return None
        
        # Store original values for audit log
        original_values = {
            "department_id": budget.department_id,
            "fiscal_year": budget.fiscal_year,
            "total_amount": str(budget.total_amount),
            "description": budget.description
        }
        
        update_data = budget_in.dict(exclude_unset=True)
        
        # If total amount is updated, recalculate remaining amount
        if "total_amount" in update_data:
            total_amount = update_data["total_amount"]
            spent_amount = budget.spent_amount
            update_data["remaining_amount"] = total_amount - spent_amount
        
        for field, value in update_data.items():
            setattr(budget, field, value)
        
        await db.commit()
        await db.refresh(budget)
        
        # Log the action
        changes = {}
        for field in original_values:
            if field in update_data and str(original_values[field]) != str(getattr(budget, field)):
                changes[field] = {
                    "old": original_values[field],
                    "new": getattr(budget, field)
                }
        
        if changes:
            await log_action_async(
                db,
                action="UPDATE",
                resource_type="BUDGET",
                resource_id=str(budget.id),
                details=changes,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
        
        logger.info(f"Updated budget ID: {budget.id}")
        return budget
    
    @staticmethod
    async def delete(
        db: AsyncSession, 
        budget_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Delete a budget.
        
        Args:
            db: Database session
            budget_id: Budget ID
            user_id: ID of the user performing the action
            ip_address: IP address of the user
            user_agent: User agent string
            
        Returns:
            True if budget was deleted, False otherwise
        """
        logger.info(f"Deleting budget with ID: {budget_id}")
        
        budget = await BudgetService.get_by_id(db, budget_id)
        if not budget:
            logger.warning(f"Budget not found for deletion, ID: {budget_id}")
            return False
        
        # Store values for audit log
        budget_values = {
            "id": budget.id,
            "department_id": budget.department_id,
            "fiscal_year": budget.fiscal_year,
            "total_amount": str(budget.total_amount),
            "description": budget.description
        }
        
        await db.delete(budget)
        await db.commit()
        
        # Log the action
        await log_action_async(
            db,
            action="DELETE",
            resource_type="BUDGET",
            resource_id=str(budget.id),
            details=budget_values,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        logger.info(f"Deleted budget ID: {budget_id}")
        return True
    
    @staticmethod
    async def update_spent_amount(
        db: AsyncSession, 
        budget_id: UUID, 
        amount_change: Decimal,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[Budget]:
        """
        Update the spent amount of a budget.
        
        This method is used when a transaction is created or updated to
        keep the budget's spent and remaining amounts in sync.
        
        Args:
            db: Database session
            budget_id: Budget ID
            amount_change: Amount to add to spent amount (can be positive or negative)
            user_id: ID of the user performing the action
            ip_address: IP address of the user
            user_agent: User agent string
            
        Returns:
            Updated budget if found, None otherwise
        """
        logger.debug(
            f"Updating spent amount for budget {budget_id} "
            f"by {amount_change}"
        )
        
        budget = await BudgetService.get_by_id(db, budget_id)
        if not budget:
            logger.warning(
                f"Budget not found for spent amount update, ID: {budget_id}"
            )
            return None
        
        # Update spent amount
        new_spent_amount = budget.spent_amount + amount_change
        
        # Ensure spent amount doesn't go negative
        if new_spent_amount < Decimal("0.00"):
            logger.warning(
                f"Attempted to set negative spent amount for budget {budget_id}"
            )
            new_spent_amount = Decimal("0.00")
        
        # Update remaining amount
        new_remaining_amount = budget.total_amount - new_spent_amount
        
        # Store original values for audit log
        original_values = {
            "spent_amount": str(budget.spent_amount),
            "remaining_amount": str(budget.remaining_amount)
        }
        
        # Apply changes
        budget.spent_amount = new_spent_amount
        budget.remaining_amount = new_remaining_amount
        
        await db.commit()
        await db.refresh(budget)
        
        # Log the action
        changes = {
            "spent_amount": {
                "old": original_values["spent_amount"],
                "new": str(budget.spent_amount)
            },
            "remaining_amount": {
                "old": original_values["remaining_amount"],
                "new": str(budget.remaining_amount)
            }
        }
        
        await log_action_async(
            db,
            action="UPDATE",
            resource_type="BUDGET",
            resource_id=str(budget.id),
            details=changes,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        logger.debug(
            f"Updated spent amount for budget {budget_id}: "
            f"spent={budget.spent_amount}, remaining={budget.remaining_amount}"
        )
        
        return budget