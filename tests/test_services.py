"""
Tests for service layer.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import Department
from app.models.user import User
from app.core.security import get_password_hash
from app.services.department import DepartmentService
from app.services.user import UserService
from app.schemas.department import DepartmentCreate
from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_department_service_create(db_session: AsyncSession):
    """Test DepartmentService.create."""
    department_data = DepartmentCreate(
        name="Computer Science",
        code="CS",
        description="Computer Science Department"
    )
    
    department = await DepartmentService.create(db_session, department_data)
    
    assert department.id is not None
    assert department.name == department_data.name
    assert department.code == department_data.code
    assert department.description == department_data.description


@pytest.mark.asyncio
async def test_department_service_get_by_id(db_session: AsyncSession):
    """Test DepartmentService.get_by_id."""
    # Create a department first
    department_data = DepartmentCreate(
        name="Computer Science",
        code="CS",
        description="Computer Science Department"
    )
    created_department = await DepartmentService.create(db_session, department_data)
    
    # Get by ID
    department = await DepartmentService.get_by_id(db_session, created_department.id)
    
    assert department is not None
    assert department.id == created_department.id
    assert department.name == created_department.name


@pytest.mark.asyncio
async def test_user_service_create(db_session: AsyncSession):
    """Test UserService.create."""
    user_data = UserCreate(
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        password="testpassword123",
        role="finance_manager"
    )
    
    user = await UserService.create(db_session, user_data)
    
    assert user.id is not None
    assert user.username == user_data.username
    assert user.email == user_data.email
    assert user.full_name == user_data.full_name
    assert user.role == user_data.role
    assert user.hashed_password != user_data.password  # Password should be hashed


@pytest.mark.asyncio
async def test_user_service_authenticate(db_session: AsyncSession):
    """Test UserService.authenticate."""
    # Create a user first
    user_data = UserCreate(
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        password="testpassword123"
    )
    await UserService.create(db_session, user_data)
    
    # Authenticate with correct credentials
    user = await UserService.authenticate(
        db_session, 
        username="testuser", 
        password="testpassword123"
    )
    assert user is not None
    assert user.username == "testuser"
    
    # Authenticate with wrong password
    user = await UserService.authenticate(
        db_session, 
        username="testuser", 
        password="wrongpassword"
    )
    assert user is None
    
    # Authenticate with non-existent user
    user = await UserService.authenticate(
        db_session, 
        username="nonexistent", 
        password="testpassword123"
    )
    assert user is None