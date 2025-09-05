"""
Tests for SQLAlchemy models.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import Department
from app.models.budget import Budget
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.core.security import get_password_hash


@pytest.mark.asyncio
async def test_create_department(db_session: AsyncSession):
    """Test creating a department."""
    department = Department(
        name="Computer Science",
        code="CS",
        description="Computer Science Department"
    )
    
    db_session.add(department)
    await db_session.commit()
    await db_session.refresh(department)
    
    assert department.id is not None
    assert department.name == "Computer Science"
    assert department.code == "CS"
    assert department.description == "Computer Science Department"


@pytest.mark.asyncio
async def test_create_budget(db_session: AsyncSession):
    """Test creating a budget."""
    # Create a department first
    department = Department(
        name="Computer Science",
        code="CS",
        description="Computer Science Department"
    )
    db_session.add(department)
    await db_session.commit()
    await db_session.refresh(department)
    
    # Create budget
    budget = Budget(
        department_id=department.id,
        fiscal_year="2023-2024",
        total_amount=100000.00,
        remaining_amount=100000.00
    )
    
    db_session.add(budget)
    await db_session.commit()
    await db_session.refresh(budget)
    
    assert budget.id is not None
    assert budget.department_id == department.id
    assert budget.fiscal_year == "2023-2024"
    assert float(budget.total_amount) == 100000.00
    assert float(budget.spent_amount) == 0.00
    assert float(budget.remaining_amount) == 100000.00


@pytest.mark.asyncio
async def test_create_transaction(db_session: AsyncSession):
    """Test creating a transaction."""
    # Create a department and budget first
    department = Department(
        name="Computer Science",
        code="CS",
        description="Computer Science Department"
    )
    db_session.add(department)
    await db_session.commit()
    await db_session.refresh(department)
    
    budget = Budget(
        department_id=department.id,
        fiscal_year="2023-2024",
        total_amount=100000.00,
        remaining_amount=100000.00
    )
    db_session.add(budget)
    await db_session.commit()
    await db_session.refresh(budget)
    
    # Create transaction
    transaction = Transaction(
        budget_id=budget.id,
        transaction_type=TransactionType.EXPENSE,
        amount=5000.00,
        description="New computers",
        reference_number="REF123"
    )
    
    db_session.add(transaction)
    await db_session.commit()
    await db_session.refresh(transaction)
    
    assert transaction.id is not None
    assert transaction.budget_id == budget.id
    assert transaction.transaction_type == TransactionType.EXPENSE
    assert float(transaction.amount) == 5000.00
    assert transaction.description == "New computers"
    assert transaction.reference_number == "REF123"


@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession):
    """Test creating a user."""
    password = "testpassword123"
    hashed_password = get_password_hash(password)
    
    user = User(
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        hashed_password=hashed_password,
        role="finance_manager"
    )
    
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    assert user.id is not None
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.full_name == "Test User"
    assert user.role == "finance_manager"
    assert user.is_active is True