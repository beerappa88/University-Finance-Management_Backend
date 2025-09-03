"""
Pydantic schemas for budgets.

This module defines the request and response schemas for budget-related
API endpoints using Pydantic models.
"""

from typing import Optional
from datetime import datetime
from decimal import Decimal
from uuid import UUID 

from pydantic import BaseModel


class BudgetBase(BaseModel):
    """Base schema for budget data."""
    
    department_id: UUID
    fiscal_year: str
    total_amount: Decimal
    description: Optional[str] = None


class BudgetCreate(BudgetBase):
    """Schema for creating a new budget."""
    
    pass


class BudgetUpdate(BaseModel):
    """Schema for updating a budget."""
    
    total_amount: Optional[Decimal] = None
    description: Optional[str] = None


class Budget(BudgetBase):
    """Schema for budget response data."""
    
    id: UUID
    spent_amount: Decimal
    remaining_amount: Decimal
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        """Configuration for the Budget schema."""
        
        orm_mode = True