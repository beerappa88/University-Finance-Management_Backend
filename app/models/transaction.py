"""
Transaction model for the university finance system.

This module defines the SQLAlchemy model for transactions,
which represent the actual spending of budgeted funds.
"""

from decimal import Decimal
from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Enum
from enum import Enum as PyEnum 
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

class TransactionType(str, PyEnum):
    """Enumeration of transaction types."""

    EXPENSE = "expense"
    REFUND = "refund"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


class Transaction(Base):
    """
    Transaction model representing a financial transaction.
    
    Transactions track the actual spending of budgeted funds, including
    expenses, refunds, and transfers between budgets.
    """
    
    __tablename__ = "transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4)
    budget_id = Column(UUID(as_uuid=True), ForeignKey("budgets.id"), nullable=False)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    description = Column(String(255), nullable=False)
    reference_number = Column(String(50), nullable=True)
    transaction_date = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships - use lazy loading
    budget = relationship("Budget", back_populates="transactions", lazy="selectin")
    
    def __repr__(self) -> str:
        """String representation of the Transaction model."""
        # Only use attributes that are always available
        return (
            f"<Transaction(id={self.id}, "
            f"budget_id={self.budget_id}, "
            f"transaction_type='{self.transaction_type.value if hasattr(self, 'transaction_type') else 'N/A'}', "
            f"amount={self.amount if hasattr(self, 'amount') else 'N/A'})>"
        )
