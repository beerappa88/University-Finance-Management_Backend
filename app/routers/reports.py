"""
Report API endpoints.
This module provides endpoints for generating and managing financial reports.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.logging import logger
from app.core.deps import require_role
from app.core.deps import get_pagination_params
from app.db.session import get_db
from app.models.user import User
from app.models.report import Report as ReportModel
from app.schemas.report import (
    Report, ReportCreate, ReportUpdate, ReportFilter, 
    ReportSummary, DashboardData
)
from app.services.report import ReportService
from app.core.rbac import can_read_report, can_create_report, can_delete_report
from app.utils.pagination import PaginationParams, PaginatedResponse, paginate_query
from uuid import UUID
import csv
import io
from fastapi.responses import StreamingResponse

router = APIRouter()

@router.get("/budget-vs-actual", response_model=Dict[str, Any])
async def generate_budget_vs_actual_report(
    fiscal_year: str = Query(..., description="Fiscal year (e.g., 2023-2024)"),
    department_id: Optional[UUID] = Query(None, description="Department ID to filter by"),
    save_report: bool = Query(False, description="Save the generated report"),
    report_name: Optional[str] = Query(None, description="Name for the saved report"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_read_report),
) -> Dict[str, Any]:
    """
    Generate a budget vs actual spending report.
    
    Args:
        fiscal_year: Fiscal year to report on
        department_id: Optional department ID to filter by
        save_report: Whether to save the generated report
        report_name: Name for the saved report
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Report data
    """
    logger.info(f"Budget vs actual report requested by: {current_user.username}")
    
    report_data = await ReportService.generate_budget_vs_actual_report(
        db, fiscal_year, department_id
    )
    
    if save_report:
        if not report_name:
            report_name = f"Budget vs Actual - {fiscal_year}"
        
        report_in = ReportCreate(
            name=report_name,
            report_type="BUDGET_VS_ACTUAL",
            parameters={
                "fiscal_year": fiscal_year,
                "department_id": str(department_id) if department_id else None
            }
        )
        
        await ReportService.save_report(db, report_in, report_data, current_user.id)
    
    logger.info("Budget vs actual report generated successfully")
    return report_data

@router.get("/department-spending", response_model=Dict[str, Any])
async def generate_department_spending_report(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    department_id: Optional[UUID] = Query(None, description="Department ID to filter by"),
    save_report: bool = Query(False, description="Save the generated report"),
    report_name: Optional[str] = Query(None, description="Name for the saved report"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_read_report),
) -> Dict[str, Any]:
    """
    Generate a department spending report.
    
    Args:
        start_date: Start date for the report
        end_date: End date for the report
        department_id: Optional department ID to filter by
        save_report: Whether to save the generated report
        report_name: Name for the saved report
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Report data
    """
    logger.info(f"Department spending report requested by: {current_user.username}")
    
    report_data = await ReportService.generate_department_spending_report(
        db, start_date, end_date, department_id
    )
    
    if save_report:
        if not report_name:
            report_name = f"Department Spending - {start_date} to {end_date}"
        
        report_in = ReportCreate(
            name=report_name,
            report_type="DEPARTMENT_SPENDING",
            parameters={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "department_id": str(department_id) if department_id else None
            }
        )
        
        await ReportService.save_report(db, report_in, report_data, current_user.id)
    
    logger.info("Department spending report generated successfully")
    return report_data

@router.get("/monthly-spending-trend", response_model=Dict[str, Any])
async def generate_monthly_spending_trend(
    fiscal_year: str = Query(..., description="Fiscal year (e.g., 2023-2024)"),
    department_id: Optional[UUID] = Query(None, description="Department ID to filter by"),
    save_report: bool = Query(False, description="Save the generated report"),
    report_name: Optional[str] = Query(None, description="Name for the saved report"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_read_report),
) -> Dict[str, Any]:
    """
    Generate a monthly spending trend report.
    
    Args:
        fiscal_year: Fiscal year to report on
        department_id: Optional department ID to filter by
        save_report: Whether to save the generated report
        report_name: Name for the saved report
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Report data
    """
    logger.info(f"Generating monthly spending trend for {fiscal_year}")
    
    report_data = await ReportService.generate_monthly_spending_trend(
        db, fiscal_year, department_id
    )
    
    if save_report:
        if not report_name:
            report_name = f"Monthly Spending Trend - {fiscal_year}"
        
        report_in = ReportCreate(
            name=report_name,
            report_type="MONTHLY_SPENDING_TREND",
            parameters={
                "fiscal_year": fiscal_year,
                "department_id": str(department_id) if department_id else None
            }
        )
        
        await ReportService.save_report(db, report_in, report_data, current_user.id)
    
    return report_data

@router.get("/expense-categories", response_model=Dict[str, Any])
async def generate_expense_categories_report(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    department_id: Optional[UUID] = Query(None, description="Department ID to filter by"),
    save_report: bool = Query(False, description="Save the generated report"),
    report_name: Optional[str] = Query(None, description="Name for the saved report"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_read_report),
) -> Dict[str, Any]:
    """
    Generate an expense categories report.
    
    Args:
        start_date: Start date for the report
        end_date: End date for the report
        department_id: Optional department ID to filter by
        save_report: Whether to save the generated report
        report_name: Name for the saved report
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Report data
    """
    logger.info(f"Generating expense categories report from {start_date} to {end_date}")
    
    report_data = await ReportService.generate_expense_categories_report(
        db, start_date, end_date, department_id
    )
    
    if save_report:
        if not report_name:
            report_name = f"Expense Categories - {start_date} to {end_date}"
        
        report_in = ReportCreate(
            name=report_name,
            report_type="EXPENSE_CATEGORIES",
            parameters={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "department_id": str(department_id) if department_id else None
            }
        )
        
        await ReportService.save_report(db, report_in, report_data, current_user.id)
    
    return report_data

@router.get("/revenue-vs-expenses", response_model=Dict[str, Any])
async def generate_revenue_vs_expenses_report(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    department_id: Optional[UUID] = Query(None, description="Department ID to filter by"),
    save_report: bool = Query(False, description="Save the generated report"),
    report_name: Optional[str] = Query(None, description="Name for the saved report"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_read_report)
) -> Dict[str, Any]:
    """
    Generate a revenue vs expenses report.
    
    Args:
        start_date: Start date for the report
        end_date: End date for the report
        department_id: Optional department ID to filter by
        save_report: Whether to save the generated report
        report_name: Name for the saved report
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Report data
    """
    logger.info(f"Generating revenue vs expenses report from {start_date} to {end_date}")
    
    report_data = await ReportService.generate_revenue_vs_expenses_report(
        db, start_date, end_date, department_id
    )
    
    if save_report:
        if not report_name:
            report_name = f"Revenue vs Expenses - {start_date} to {end_date}"
        
        report_in = ReportCreate(
            name=report_name,
            report_type="REVENUE_VS_EXPENSES",
            parameters={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "department_id": str(department_id) if department_id else None
            }
        )
        
        await ReportService.save_report(db, report_in, report_data, current_user.id)
    
    return report_data

# Generic routes should come AFTER specific routes
@router.get("/", response_model=PaginatedResponse[Report])
async def get_saved_reports(
    request: Request,
    db: AsyncSession = Depends(get_db),
    pagination: PaginationParams = Depends(get_pagination_params),
    report_type: Optional[str] = Query(None),
    generated_by: Optional[UUID] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(can_read_report),
) -> PaginatedResponse[Report]:
    """
    Get all saved reports with filtering capabilities and pagination.
    """
    logger.debug("Getting saved reports with filters")
    
    # Base query
    stmt = select(ReportModel)
    
    # Apply filters
    if report_type:
        stmt = stmt.where(ReportModel.report_type == report_type)
    
    if generated_by:
        stmt = stmt.where(ReportModel.generated_by == generated_by)
    
    if start_date:
        stmt = stmt.where(ReportModel.created_at >= start_date)
    
    if end_date:
        stmt = stmt.where(ReportModel.created_at <= end_date)
    
    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(
            ReportModel.name.ilike(search_term)
        )
    
    # Create count query for performance
    count_query = select(func.count(ReportModel.id))
    if report_type:
        count_query = count_query.where(ReportModel.report_type == report_type)
    
    if generated_by:
        count_query = count_query.where(ReportModel.generated_by == generated_by)
    
    if start_date:
        count_query = count_query.where(ReportModel.created_at >= start_date)
    
    if end_date:
        count_query = count_query.where(ReportModel.created_at <= end_date)
    
    if search:
        search_term = f"%{search}%"
        count_query = count_query.where(
            ReportModel.name.ilike(search_term)
        )
    
    # Execute paginated query
    result = await paginate_query(db, stmt, pagination, count_query, ReportModel)
    
    logger.info(f"Retrieved {len(result.items)} reports (page {result.page} of {result.pages})")
    
    return result

@router.get("/summary", response_model=ReportSummary)
async def get_reports_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_read_report),
) -> ReportSummary:
    """
    Get a summary of reports statistics.
    """
    logger.debug("Getting reports summary")
    return await ReportService.get_report_summary(db)

@router.get("/statistics", response_model=Dict[str, Any])
async def get_report_statistics(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_read_report),
) -> Dict[str, Any]:
    """
    Get report generation statistics for the last N days.
    """
    logger.debug(f"Getting report statistics for {days} days")
    return await ReportService.get_report_statistics(db, days)

@router.post("/cleanup", response_model=Dict[str, Any])
async def cleanup_old_reports(
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
) -> Dict[str, Any]:
    """
    Delete reports older than specified days (Admin only).
    """
    logger.debug(f"Cleaning up reports older than {days} days")
    
    count = await ReportService.cleanup_old_reports(db, days)
    
    return {
        "message": f"Deleted {count} old reports",
        "deleted_count": count,
        "cutoff_days": days
    }

@router.get("/{report_id}", response_model=Report)
async def get_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_read_report),
) -> Report:
    """
    Get a saved report by ID.
    """
    logger.debug(f"Getting report by ID: {report_id}")
    
    report = await ReportService.get_report_by_id(db, report_id)
    if not report:
        logger.warning(f"Report not found, ID: {report_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    return report

@router.put("/{report_id}", response_model=Report)
async def update_report(
    report_id: UUID,
    report_update: ReportUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_create_report),
) -> Report:
    """
    Update a report's name or parameters.
    """
    logger.debug(f"Updating report: {report_id}")
    
    report = await ReportService.update_report(db, report_id, report_update)
    if not report:
        logger.warning(f"Report not found for update, ID: {report_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    return report

@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_delete_report),
):
    """
    Delete a report.
    """
    logger.debug(f"Deleting report: {report_id}")
    
    deleted = await ReportService.delete_report(db, report_id)
    if not deleted:
        logger.warning(f"Report not found for deletion, ID: {report_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )

@router.get("/exports/{report_type}/{report_id}")
async def export_report_endpoint(
    report_type: str,
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(can_read_report),
):
    """
    Export a report as CSV.
    
    Args:
        report_type: Type of report
        report_id: Report ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        CSV file download
    """
    try:
        # Fetch the report
        report_result = await db.execute(
            select(ReportModel).where(ReportModel.id == report_id)
        )
        report = report_result.scalars().first()
        
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )
        
        # Check if report has results
        if not report.results:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Report has no exportable data"
            )
        
        # Try to get table data, fall back to other data structures
        table_data = None
        if report.results.get('tableData'):
            table_data = report.results.get('tableData', {})
        elif report.results.get('chartData'):
            # If no table data, try to create from chart data
            chart_data = report.results.get('chartData', {})
            if chart_data.get('labels') and chart_data.get('datasets'):
                # Create table from chart data
                labels = chart_data.get('labels', [])
                datasets = chart_data.get('datasets', [])
                
                # Create headers
                headers = ['Category'] + [dataset.get('label', f'Dataset {i+1}') for i, dataset in enumerate(datasets)]
                
                # Create rows
                rows = []
                for i, label in enumerate(labels):
                    row = [label]
                    for dataset in datasets:
                        data = dataset.get('data', [])
                        row.append(data[i] if i < len(data) else 0)
                    rows.append(row)
                
                table_data = {
                    'headers': headers,
                    'rows': rows
                }
        else:
            # Try to extract data from other possible structures
            # This is a fallback for reports that don't have tableData or chartData
            results = report.results
            if isinstance(results, dict):
                # Look for any data that could be converted to a table
                for key, value in results.items():
                    if isinstance(value, list) and len(value) > 0:
                        # Assume this is a list of rows
                        if isinstance(value[0], dict):
                            # If rows are dictionaries, use keys as headers
                            headers = list(value[0].keys())
                            rows = [[row.get(header, '') for header in headers] for row in value]
                            table_data = {
                                'headers': headers,
                                'rows': rows
                            }
                            break
                        elif isinstance(value[0], list):
                            # If rows are lists, assume first row is headers
                            headers = value[0]
                            rows = value[1:]
                            table_data = {
                                'headers': headers,
                                'rows': rows
                            }
                            break
        
        if not table_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Report has no exportable data format"
            )
        
        headers = table_data.get('headers', [])
        rows = table_data.get('rows', [])
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(headers)
        
        # Write rows
        for row in rows:
            writer.writerow(row)
        
        # Prepare response
        csv_content = output.getvalue()
        output.close()
        
        # Return CSV file as streaming response
        def iterfile():
            yield csv_content.encode('utf-8')
        
        return StreamingResponse(
            iterfile(),
            media_type="text/csv",
            headers={
                'Content-Disposition': f'attachment; filename="{report_type}_report_{report_id}.csv"'
            }
        )
    except HTTPException:
        # Re-raise HTTP exceptions as they are
        raise
    except Exception as e:
        # Log the full exception for debugging
        logger.error(f"Error exporting report {report_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export report: {str(e)}"
        )
