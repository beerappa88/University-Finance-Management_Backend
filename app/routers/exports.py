"""
Export endpoints for reports.
This module provides endpoints for exporting reports in different formats.
"""
from typing import List, Dict, Any, Optional
from datetime import date, datetime
from io import StringIO
import csv
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from app.core.logging import logger
from app.db.session import get_db
from app.core.auth import get_current_active_user
from app.models.user import User
from app.models.export_history import ExportHistory
from app.services.report import ReportService
from app.core.rbac import can_read_budget, can_read_transaction, can_read_report, can_read_department
from app.utils.pagination import PaginationParams, paginate_query
from uuid import UUID

router = APIRouter()

# Helper function to save export history
async def save_export_record(
    db: AsyncSession,
    user_id: uuid.UUID,
    export_type: str,
    name: str,
    params: Dict[str, Any],
    status: str = "completed"
) -> ExportHistory:
    """
    Save an export record to the database.
    """
    export_record = ExportHistory(
        id=uuid.uuid4(),
        user_id=user_id,
        export_type=export_type,
        name=name,
        params=json.dumps(params),
        status=status,
        timestamp=datetime.utcnow()
    )
    db.add(export_record)
    await db.commit()
    await db.refresh(export_record)
    return export_record

# Get export history endpoint
@router.get("/history")
async def get_export_history(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get export history for the current user with pagination.
    """
    # Build the base query
    query = select(ExportHistory).where(ExportHistory.user_id == current_user.id)
    
    # Apply search if provided
    if pagination.search:
        search_term = f"%{pagination.search}%"
        query = query.where(
            or_(
                ExportHistory.name.ilike(search_term),
                ExportHistory.export_type.ilike(search_term)
            )
        )
    
    # Count query for total records
    count_query = select(func.count(ExportHistory.id)).where(ExportHistory.user_id == current_user.id)
    if pagination.search:
        count_query = count_query.where(
            or_(
                ExportHistory.name.ilike(search_term),
                ExportHistory.export_type.ilike(search_term)
            )
        )
    
    # Paginate the query
    result = await paginate_query(
        db=db,
        query=query,
        pagination=pagination,
        count_query=count_query,
        model=ExportHistory
    )
    
    # Format the items for the response
    formatted_items = []
    for item in result.items:
        formatted_item = {
            "id": str(item.id),
            "export_type": item.export_type,
            "name": item.name,
            "timestamp": item.timestamp.isoformat(),
            "status": item.status,
            "params": json.loads(item.params) if item.params else {}
        }
        formatted_items.append(formatted_item)
    
    # Return the paginated response
    return {
        "items": formatted_items,
        "total": result.total,
        "page": result.page,
        "size": result.size,
        "pages": result.pages,
        "has_next": result.has_next,
        "has_prev": result.has_prev
    }

# Clear export history endpoint
@router.delete("/history")
async def clear_export_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, str]:
    """
    Clear export history for the current user.
    """
    # Delete all export history records for the current user
    await db.execute(
        select(ExportHistory).where(ExportHistory.user_id == current_user.id)
        .execution_options(synchronize_session="fetch")
    )
    await db.commit()
    
    return {"message": "Export history cleared successfully"}

@router.get("/budget-vs-actual/csv")
async def export_budget_vs_actual_csv(
    fiscal_year: str = Query(..., description="Fiscal year (e.g., 2023-2024)"),
    department_id: Optional[UUID] = Query(None, description="Department ID to filter by"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_read_budget),
) -> StreamingResponse:
    """
    Export budget vs actual report as CSV.
    """
    logger.info(f"Exporting budget vs actual report as CSV for {fiscal_year}")
    
    try:
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
        
        # Save export record
        await save_export_record(
            db=db,
            user_id=current_user.id,
            export_type="budget-vs-actual",
            name=f"Budget vs Actual - {fiscal_year}",
            params={"fiscal_year": fiscal_year, "department_id": str(department_id) if department_id else None}
        )
        
        # Return as streaming response
        return StreamingResponse(
            iter([output.getvalue().encode('utf-8')]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=budget_vs_actual_{fiscal_year}.csv"}
        )
    except Exception as e:
        logger.error(f"Error exporting budget vs actual: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate budget vs actual report"
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
    """
    logger.info(f"Exporting department spending report as CSV from {start_date} to {end_date}")
    
    try:
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
        
        # Save export record
        await save_export_record(
            db=db,
            user_id=current_user.id,
            export_type="department-spending",
            name=f"Department Spending - {start_date} to {end_date}",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "department_id": str(department_id) if department_id else None
            }
        )
        
        # Return as streaming response
        return StreamingResponse(
            iter([output.getvalue().encode('utf-8')]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=department_spending_{start_date}_to_{end_date}.csv"}
        )
    except Exception as e:
        logger.error(f"Error exporting department spending: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate department spending report"
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
    """
    logger.info(f"Exporting transactions as CSV from {start_date} to {end_date}")
    
    try:
        # Get transactions
        from app.models.transaction import Transaction, TransactionType
        from app.models.budget import Budget
        from app.models.department import Department
        
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
        
        # Save export record
        await save_export_record(
            db=db,
            user_id=current_user.id,
            export_type="transactions",
            name=f"Transactions - {start_date} to {end_date}",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "department_id": str(department_id) if department_id else None,
                "budget_id": str(budget_id) if budget_id else None
            }
        )
        
        # Return as streaming response
        return StreamingResponse(
            iter([output.getvalue().encode('utf-8')]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=transactions_{start_date}_to_{end_date}.csv"}
        )
    except Exception as e:
        logger.error(f"Error exporting transactions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export transactions"
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
    """
    logger.info(f"Exporting expense categories report as CSV from {start_date} to {end_date}")
    
    try:
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
        
        # Save export record
        await save_export_record(
            db=db,
            user_id=current_user.id,
            export_type="expense-categories",
            name=f"Expense Categories - {start_date} to {end_date}",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "department_id": str(department_id) if department_id else None
            }
        )
        
        # Return as streaming response
        return StreamingResponse(
            iter([output.getvalue().encode('utf-8')]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=expense_categories_{start_date}_to_{end_date}.csv"}
        )
    except Exception as e:
        logger.error(f"Error exporting expense categories: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate expense categories report"
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
    """
    logger.info(f"Exporting revenue vs expenses report as CSV from {start_date} to {end_date}")
    
    try:
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
        
        # Save export record
        await save_export_record(
            db=db,
            user_id=current_user.id,
            export_type="revenue-vs-expenses",
            name=f"Revenue vs Expenses - {start_date} to {end_date}",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "department_id": str(department_id) if department_id else None
            }
        )
        
        # Return as streaming response
        return StreamingResponse(
            iter([output.getvalue().encode('utf-8')]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=revenue_vs_expenses_{start_date}_to_{end_date}.csv"}
        )
    except Exception as e:
        logger.error(f"Error exporting revenue vs expenses: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate revenue vs expenses report"
        )
