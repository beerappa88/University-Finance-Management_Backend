"""
Tests for dashboard functionality.
"""

import pytest
from fastapi import status

from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_get_dashboard_data(async_client):
    """Test getting dashboard data."""
    # Setup: create user, department, budget, transactions
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
    
    # Get dashboard data
    response = await async_client.get("/dashboard/", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    
    dashboard_data = response.json()
    assert dashboard_data["total_departments"] >= 1
    assert dashboard_data["total_budgets"] >= 1
    assert dashboard_data["total_transactions"] >= 1
    assert dashboard_data["total_budget_amount"] == 100000.00
    assert dashboard_data["total_spent_amount"] == 5000.00
    assert dashboard_data["budget_utilization_percent"] == 5.0
    assert len(dashboard_data["recent_transactions"]) >= 1
    assert len(dashboard_data["top_spending_departments"]) >= 1
    assert len(dashboard_data["monthly_spending_trend"]) == 12