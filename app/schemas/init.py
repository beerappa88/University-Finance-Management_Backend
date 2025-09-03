"""
Schemas package initialization.

This module imports all schemas to make them available from a single import point.
"""

from app.schemas.department import (
    DepartmentBase,
    DepartmentCreate,
    DepartmentUpdate,
    Department,
)
from app.schemas.budget import (
    BudgetBase,
    BudgetCreate,
    BudgetUpdate,
    Budget,
)
from app.schemas.transaction import (
    TransactionBase,
    TransactionCreate,
    TransactionUpdate,
    Transaction
)

from app.schemas.report import (
    ReportBase,
    ReportCreate,
    Report,
    DashboardData
)

from app.schemas.user import (
    UserBase,
    UserCreate,
    UserUpdate,
    User,
    UserInDB,
    Token,
    TokenData
)

__all__ = [
    # Department schemas
    "DepartmentBase",
    "DepartmentCreate",
    "DepartmentUpdate",
    "Department",
    # Budget schemas
    "BudgetBase",
    "BudgetCreate",
    "BudgetUpdate",
    "Budget",
    # Transaction schemas
    "TransactionBase",
    "TransactionCreate",
    "TransactionUpdate",
    "Transaction",
    # Report schemas
    "ReportBase",
    "ReportCreate",
    "Report",
    "DashboardData",
    # User schemas
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "User",
    "UserInDB",
    "Token",
    "TokenData",
    # Add any other schemas here
]