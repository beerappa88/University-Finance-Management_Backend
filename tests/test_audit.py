"""
Tests for audit logging functionality.
"""

import pytest
from fastapi import status
from unittest.mock import patch

from app.models.audit import AuditLog
from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_audit_log_on_user_creation(async_client):
    """Test that user creation is logged in audit logs."""
    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "full_name": "Test User",
        "password": "testpassword123",
        "role": "finance_manager"
    }
    
    response = await async_client.post("/auth/register", json=user_data)
    assert response.status_code == status.HTTP_201_CREATED
    
    # Check audit log was created
    from app.db.session import TestSessionLocal
    async with TestSessionLocal() as db:
        result = await db.execute(
            "SELECT * FROM audit_logs WHERE action = 'CREATE' AND resource_type = 'USER'"
        )
        audit_log = result.fetchone()
        assert audit_log is not None
        assert audit_log.details["username"] == user_data["username"]


@pytest.mark.asyncio
async def test_audit_log_on_department_creation(async_client):
    """Test that department creation is logged in audit logs."""
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
    
    # Check audit log was created
    from app.db.session import TestSessionLocal
    async with TestSessionLocal() as db:
        result = await db.execute(
            "SELECT * FROM audit_logs WHERE action = 'CREATE' AND resource_type = 'DEPARTMENT'"
        )
        audit_log = result.fetchone()
        assert audit_log is not None
        assert audit_log.details["name"] == department_data["name"]


@pytest.mark.asyncio
async def test_audit_log_on_transaction_creation(async_client):
    """Test that transaction creation is logged in audit logs."""
    # Setup: create user, department, budget
    await test_create_department_success(async_client)
    
    # Login as finance manager
    form_data = {
        "username": "finance_manager",
        "password": "testpassword123"
    }
    token_response = await async_client.post("/auth/token", data=form_data)
    token = token_response.json()["access_token"]
    
    # Create budget
    budget_data = {
        "department_id": 1,
        "fiscal_year": "2023-2024",
        "total_amount": 100000.00,
        "description": "Computer Science Budget"
    }
    
    headers = {"Authorization": f"Bearer {token}"}
    response = await async_client.post("/budgets/", json=budget_data, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED
    
    budget_id = response.json()["id"]
    
    # Create transaction
    transaction_data = {
        "budget_id": budget_id,
        "transaction_type": "expense",
        "amount": 5000.00,
        "description": "New computers",
        "reference_number": "REF123"
    }
    
    response = await async_client.post("/transactions/", json=transaction_data, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED
    
    # Check audit log was created
    from app.db.session import TestSessionLocal
    async with TestSessionLocal() as db:
        result = await db.execute(
            "SELECT * FROM audit_logs WHERE action = 'CREATE' AND resource_type = 'TRANSACTION'"
        )
        audit_log = result.fetchone()
        assert audit_log is not None
        assert audit_log.details["amount"] == "5000.00"
        assert audit_log.details["description"] == "New computers"


@pytest.mark.asyncio
async def test_audit_log_with_ip_and_user_agent(async_client):
    """Test that IP address and user agent are logged in audit logs."""
    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "full_name": "Test User",
        "password": "testpassword123"
    }
    
    # Mock request with IP and user agent
    with patch('fastapi.Request') as mock_request:
        mock_request.client.host = "192.168.1.1"
        mock_request.headers.get.return_value = "Mozilla/5.0 Test Browser"
        
        response = await async_client.post("/auth/register", json=user_data)
        assert response.status_code == status.HTTP_201_CREATED
        
        # Check audit log includes IP and user agent
        from app.db.session import TestSessionLocal
        async with TestSessionLocal() as db:
            result = await db.execute(
                "SELECT * FROM audit_logs WHERE action = 'CREATE' AND resource_type = 'USER'"
            )
            audit_log = result.fetchone()
            assert audit_log is not None
            assert audit_log.ip_address == "192.168.1.1"
            assert audit_log.user_agent == "Mozilla/5.0 Test Browser"