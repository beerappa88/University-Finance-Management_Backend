"""
Pydantic schemas for transactions.

This module defines the request and response schemas for transaction-related
API endpoints using Pydantic models.
"""

from typing import Optional
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.models.transaction import TransactionType


class TransactionBase(BaseModel):
    """Base schema for transaction data."""
    
    budget_id: UUID
    transaction_type: TransactionType
    amount: Decimal
    description: str
    reference_number: Optional[str] = None
    transaction_date: Optional[datetime] = None


class TransactionCreate(TransactionBase):
    """Schema for creating a new transaction."""
    
    pass


class TransactionUpdate(BaseModel):
    """Schema for updating a transaction."""
    
    amount: Optional[Decimal] = None
    description: Optional[str] = None
    reference_number: Optional[str] = None
    transaction_date: Optional[datetime] = None


class Transaction(TransactionBase):
    """Schema for transaction response data."""
    
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        """Configuration for the Transaction schema."""
        
        orm_mode = True