"""
Export endpoints for reports.
This module provides endpoints for exporting reports in different formats.
"""
from typing import List, Dict, Any, Optional
from datetime import date
from io import StringIO
import csv
import json
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import logger
from app.db.session import get_db
from app.core.auth import get_current_active_user
from app.models.user import User
from app.services.report import ReportService
from app.core.rbac import can_read_budget, can_read_transaction, can_read_report, can_read_department
from uuid import UUID

router = APIRouter()

@router.get("/budget-vs-actual/csv")
async def export_budget_vs_actual_csv(
    fiscal_year: str = Query(..., description="Fiscal year (e.g., 2023-2024)"),
    department_id: Optional[UUID] = Query(None, description="Department ID to filter by"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_read_budget),
) -> StreamingResponse:
    """
    Export budget vs actual report as CSV.
    
    Args:
        fiscal_year: Fiscal year to report on
        department_id: Optional department ID to filter by
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        CSV file
    """
    logger.info(f"Exporting budget vs actual report as CSV for {fiscal_year}")
    
    # Generate report
    report_data = await ReportService.generate_budget_vs_actual_report(
        db, fiscal_year, department_id
    )
    
    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "Department ID", "Department Name", "Budget ID", 
        "Total Budget", "Total Spent", "Remaining", "Utilization %"
    ])
    
    # Write department data
    for dept in report_data["departments"]:
        writer.writerow([
            dept["department_id"],
            dept["department_name"],
            dept["budget_id"],
            dept["total_budget"],
            dept["total_spent"],
            dept["remaining"],
            dept["utilization_percent"]
        ])
    
    # Write summary
    writer.writerow([])
    writer.writerow(["Summary"])
    writer.writerow(["Total Budget", report_data["summary"]["total_budget"]])
    writer.writerow(["Total Spent", report_data["summary"]["total_spent"]])
    writer.writerow(["Total Remaining", report_data["summary"]["total_remaining"]])
    writer.writerow(["Overall Utilization %", report_data["summary"]["overall_utilization_percent"]])
    
    # Reset file pointer
    output.seek(0)
    
    # Return as streaming response
    return StreamingResponse(
        iter([output.getvalue().encode('utf-8')]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=budget_vs_actual_{fiscal_year}.csv"}
    )

@router.get("/department-spending/csv")
async def export_department_spending_csv(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    department_id: Optional[UUID] = Query(None, description="Department ID to filter by"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_read_department),
) -> StreamingResponse:
    """
    Export department spending report as CSV.
    
    Args:
        start_date: Start date for the report
        end_date: End date for the report
        department_id: Optional department ID to filter by
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        CSV file
    """
    logger.info(f"Exporting department spending report as CSV from {start_date} to {end_date}")
    
    # Generate report
    report_data = await ReportService.generate_department_spending_report(
        db, start_date, end_date, department_id
    )
    
    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "Department ID", "Department Name", "Expenses", "Refunds", 
        "Transfers In", "Transfers Out", "Net Spending", "Transaction Count"
    ])
    
    # Write department data
    for dept in report_data["departments"]:
        writer.writerow([
            dept["department_id"],
            dept["department_name"],
            dept["expenses"],
            dept["refunds"],
            dept["transfers_in"],
            dept["transfers_out"],
            dept["net_spending"],
            dept["transaction_count"]
        ])
    
    # Write summary
    writer.writerow([])
    writer.writerow(["Summary"])
    writer.writerow(["Total Expenses", report_data["summary"]["total_expenses"]])
    writer.writerow(["Total Refunds", report_data["summary"]["total_refunds"]])
    writer.writerow(["Total Transfers In", report_data["summary"]["total_transfers_in"]])
    writer.writerow(["Total Transfers Out", report_data["summary"]["total_transfers_out"]])
    writer.writerow(["Total Net Spending", report_data["summary"]["total_net_spending"]])
    writer.writerow(["Total Transactions", report_data["summary"]["total_transactions"]])
    
    # Reset file pointer
    output.seek(0)
    
    # Return as streaming response
    return StreamingResponse(
        iter([output.getvalue().encode('utf-8')]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=department_spending_{start_date}_to_{end_date}.csv"}
    )

@router.get("/transactions/csv")
async def export_transactions_csv(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    department_id: Optional[UUID] = Query(None, description="Department ID to filter by"),
    budget_id: Optional[UUID] = Query(None, description="Budget ID to filter by"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_read_transaction),
) -> StreamingResponse:
    """
    Export transactions as CSV.
    
    Args:
        start_date: Start date for the report
        end_date: End date for the report
        department_id: Optional department ID to filter by
        budget_id: Optional budget ID to filter by
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        CSV file
    """
    logger.info(f"Exporting transactions as CSV from {start_date} to {end_date}")
    
    # Get transactions
    from app.models.transaction import Transaction, TransactionType
    from app.models.budget import Budget
    from app.models.department import Department
    from sqlalchemy import select, and_
    
    # Build query
    query = select(
        Transaction,
        Budget,
        Department
    ).join(
        Budget, Transaction.budget_id == Budget.id
    ).join(
        Department, Budget.department_id == Department.id
    ).where(
        and_(
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        )
    )
    
    if department_id:
        query = query.where(Budget.department_id == department_id)
    
    if budget_id:
        query = query.where(Transaction.budget_id == budget_id)
    
    result = await db.execute(query)
    transactions = result.all()
    
    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "Transaction ID", "Budget ID", "Department", "Type", 
        "Amount", "Description", "Reference Number", "Date"
    ])
    
    # Write transaction data
    for transaction, budget, department in transactions:
        writer.writerow([
            transaction.id,
            transaction.budget_id,
            department.name,
            transaction.transaction_type.value,
            transaction.amount,
            transaction.description,
            transaction.reference_number or "",
            transaction.transaction_date.isoformat()
        ])
    
    # Reset file pointer
    output.seek(0)
    
    # Return as streaming response
    return StreamingResponse(
        iter([output.getvalue().encode('utf-8')]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=transactions_{start_date}_to_{end_date}.csv"}
    )

@router.get("/expense-categories/csv")
async def export_expense_categories_csv(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    department_id: Optional[UUID] = Query(None, description="Department ID to filter by"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    """
    Export expense categories report as CSV.
    
    Args:
        start_date: Start date for the report
        end_date: End date for the report
        department_id: Optional department ID to filter by
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        CSV file
    """
    logger.info(f"Exporting expense categories report as CSV from {start_date} to {end_date}")
    
    # Generate report
    report_data = await ReportService.generate_expense_categories_report(
        db, start_date, end_date, department_id
    )
    
    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "Category", "Total Amount", "Transaction Count", "Percentage"
    ])
    
    # Write category data
    for category in report_data["categories"]:
        writer.writerow([
            category["category"],
            category["total_amount"],
            category["transaction_count"],
            f"{(category['total_amount'] / report_data['summary']['total_amount'] * 100):.2f}%"
        ])
    
    # Write summary
    writer.writerow([])
    writer.writerow(["Summary"])
    writer.writerow(["Total Amount", report_data["summary"]["total_amount"]])
    writer.writerow(["Total Transactions", report_data["summary"]["total_transactions"]])
    writer.writerow(["Category Count", report_data["summary"]["category_count"]])
    
    # Reset file pointer
    output.seek(0)
    
    # Return as streaming response
    return StreamingResponse(
        iter([output.getvalue().encode('utf-8')]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=expense_categories_{start_date}_to_{end_date}.csv"}
    )

@router.get("/revenue-vs-expenses/csv")
async def export_revenue_vs_expenses_csv(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    department_id: Optional[UUID] = Query(None, description="Department ID to filter by"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> StreamingResponse:
    """
    Export revenue vs expenses report as CSV.
    
    Args:
        start_date: Start date for the report
        end_date: End date for the report
        department_id: Optional department ID to filter by
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        CSV file
    """
    logger.info(f"Exporting revenue vs expenses report as CSV from {start_date} to {end_date}")
    
    # Generate report
    report_data = await ReportService.generate_revenue_vs_expenses_report(
        db, start_date, end_date, department_id
    )
    
    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "Month", "Revenue", "Expenses", "Net"
    ])
    
    # Write monthly data
    for month in report_data["monthly"]:
        writer.writerow([
            month["month_name"],
            month["revenue"],
            month["expenses"],
            month["net"]
        ])
    
    # Write summary
    writer.writerow([])
    writer.writerow(["Summary"])
    writer.writerow(["Total Revenue", report_data["summary"]["total_revenue"]])
    writer.writerow(["Total Expenses", report_data["summary"]["total_expenses"]])
    writer.writerow(["Total Net", report_data["summary"]["total_net"]])
    writer.writerow(["Net Margin %", f"{report_data['summary']['net_margin']:.2f}%"])
    
    # Reset file pointer
    output.seek(0)
    
    # Return as streaming response
    return StreamingResponse(
        iter([output.getvalue().encode('utf-8')]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=revenue_vs_expenses_{start_date}_to_{end_date}.csv"}
    )
