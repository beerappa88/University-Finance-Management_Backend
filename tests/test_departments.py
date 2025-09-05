"""
Tests for department endpoints.
"""

import pytest
from fastapi import status

from app.schemas.department import DepartmentCreate


@pytest.mark.asyncio
async def test_create_department_unauthorized(async_client):
    """Test creating a department without authentication."""
    department_data = {
        "name": "Computer Science",
        "code": "CS",
        "description": "Computer Science Department"
    }
    
    response = await async_client.post("/departments/", json=department_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_create_department_insufficient_permissions(async_client):
    """Test creating a department with insufficient permissions."""
    # Register and login a viewer user
    user_data = {
        "username": "viewer",
        "email": "viewer@example.com",
        "full_name": "Viewer User",
        "password": "testpassword123",
        "role": "viewer"
    }
    await async_client.post("/auth/register", json=user_data)
    
    form_data = {
        "username": "viewer",
        "password": "testpassword123"
    }
    token_response = await async_client.post("/auth/token", data=form_data)
    token = token_response.json()["access_token"]
    
    # Try to create department
    department_data = {
        "name": "Computer Science",
        "code": "CS",
        "description": "Computer Science Department"
    }
    
    headers = {"Authorization": f"Bearer {token}"}
    response = await async_client.post("/departments/", json=department_data, headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Not enough permissions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_department_success(async_client):
    """Test creating a department with sufficient permissions."""
    # Register and login a finance manager
    user_data = {
        "username": "finance_manager",
        "email": "finance@example.com",
        "full_name": "Finance Manager",
        "password": "testpassword123",
        "role": "finance_manager"
    }
    await async_client.post("/auth/register", json=user_data)
    
    form_data = {
        "username": "finance_manager",
        "password": "testpassword123"
    }
    token_response = await async_client.post("/auth/token", data=form_data)
    token = token_response.json()["access_token"]
    
    # Create department
    department_data = {
        "name": "Computer Science",
        "code": "CS",
        "description": "Computer Science Department"
    }
    
    headers = {"Authorization": f"Bearer {token}"}
    response = await async_client.post("/departments/", json=department_data, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED
    
    data = response.json()
    assert data["name"] == department_data["name"]
    assert data["code"] == department_data["code"]
    assert data["description"] == department_data["description"]


@pytest.mark.asyncio
async def test_get_departments(async_client):
    """Test getting all departments."""
    # Create a department first
    await test_create_department_success(async_client)
    
    # Get departments without authentication
    response = await async_client.get("/departments/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # Login as viewer
    user_data = {
        "username": "viewer",
        "email": "viewer@example.com",
        "full_name": "Viewer User",
        "password": "testpassword123",
        "role": "viewer"
    }
    await async_client.post("/auth/register", json=user_data)
    
    form_data = {
        "username": "viewer",
        "password": "testpassword123"
    }
    token_response = await async_client.post("/auth/token", data=form_data)
    token = token_response.json()["access_token"]
    
    # Get departments with authentication
    headers = {"Authorization": f"Bearer {token}"}
    response = await async_client.get("/departments/", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert len(data) >= 1
    assert data[0]["name"] == "Computer Science"