"""
Tests for reporting functionality.
"""

import pytest
from fastapi import status
from datetime import date

from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_generate_budget_vs_actual_report(async_client):
    """Test generating a budget vs actual report."""
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
    
    # Generate report
    response = await async_client.get(
        "/reports/budget-vs-actual?fiscal_year=2023-2024",
        headers=headers
    )
    assert response.status_code == status.HTTP_200_OK
    
    report_data = response.json()
    assert report_data["fiscal_year"] == "2023-2024"
    assert len(report_data["departments"]) > 0
    assert report_data["summary"]["total_budget"] == 100000.00
    assert report_data["summary"]["total_spent"] == 5000.00


@pytest.mark.asyncio
async def test_generate_department_spending_report(async_client):
    """Test generating a department spending report."""
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
    
    # Generate report
    response = await async_client.get(
        "/reports/department-spending?start_date=2023-01-01&end_date=2023-12-31",
        headers=headers
    )
    assert response.status_code == status.HTTP_200_OK
    
    report_data = response.json()
    assert report_data["start_date"] == "2023-01-01"
    assert report_data["end_date"] == "2023-12-31"
    assert len(report_data["departments"]) > 0
    assert report_data["summary"]["total_expenses"] == 5000.00


@pytest.mark.asyncio
async def test_save_report(async_client):
    """Test saving a generated report."""
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
    
    # Generate and save report
    response = await async_client.get(
        "/reports/budget-vs-actual?fiscal_year=2023-2024&save_report=true&report_name=Test Report",
        headers=headers
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Get saved reports
    response = await async_client.get("/reports/", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    
    reports = response.json()
    assert len(reports) > 0
    assert reports[0]["name"] == "Test Report"
    assert reports[0]["report_type"] == "BUDGET_VS_ACTUAL"