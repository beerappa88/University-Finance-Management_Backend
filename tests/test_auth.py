"""
Tests for authentication endpoints.
"""

import pytest
from fastapi import status

from app.core.security import create_access_token
from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_register_user(async_client):
    """Test user registration."""
    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "full_name": "Test User",
        "password": "testpassword123",
        "role": "finance_manager"
    }
    
    response = await async_client.post("/auth/register", json=user_data)
    assert response.status_code == status.HTTP_201_CREATED
    
    data = response.json()
    assert data["username"] == user_data["username"]
    assert data["email"] == user_data["email"]
    assert data["full_name"] == user_data["full_name"]
    assert data["role"] == user_data["role"]
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_username(async_client):
    """Test registration with duplicate username."""
    user_data = {
        "username": "testuser",
        "email": "test1@example.com",
        "full_name": "Test User",
        "password": "testpassword123"
    }
    
    # Register first user
    await async_client.post("/auth/register", json=user_data)
    
    # Try to register with same username
    user_data["email"] = "test2@example.com"
    response = await async_client.post("/auth/register", json=user_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Username already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_email(async_client):
    """Test registration with duplicate email."""
    user_data = {
        "username": "testuser1",
        "email": "test@example.com",
        "full_name": "Test User",
        "password": "testpassword123"
    }
    
    # Register first user
    await async_client.post("/auth/register", json=user_data)
    
    # Try to register with same email
    user_data["username"] = "testuser2"
    response = await async_client.post("/auth/register", json=user_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Email already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_for_access_token(async_client):
    """Test user login."""
    # Register a user first
    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "full_name": "Test User",
        "password": "testpassword123"
    }
    await async_client.post("/auth/register", json=user_data)
    
    # Login
    form_data = {
        "username": "testuser",
        "password": "testpassword123"
    }
    response = await async_client.post("/auth/token", data=form_data)
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_credentials(async_client):
    """Test login with invalid credentials."""
    form_data = {
        "username": "nonexistent",
        "password": "wrongpassword"
    }
    response = await async_client.post("/auth/token", data=form_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Incorrect username or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_read_users_me(async_client):
    """Test getting current user info."""
    # Register and login a user
    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "full_name": "Test User",
        "password": "testpassword123"
    }
    await async_client.post("/auth/register", json=user_data)
    
    form_data = {
        "username": "testuser",
        "password": "testpassword123"
    }
    token_response = await async_client.post("/auth/token", data=form_data)
    token = token_response.json()["access_token"]
    
    # Get user info
    headers = {"Authorization": f"Bearer {token}"}
    response = await async_client.get("/auth/me", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert data["username"] == user_data["username"]
    assert data["email"] == user_data["email"]
    assert data["full_name"] == user_data["full_name"]


@pytest.mark.asyncio
async def test_read_users_me_unauthorized(async_client):
    """Test getting user info without token."""
    response = await async_client.get("/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED