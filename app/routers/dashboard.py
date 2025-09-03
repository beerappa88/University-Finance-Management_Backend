"""
Dashboard API endpoints.

This module provides endpoints for dashboard data visualization and analytics.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, date
from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, extract, case, cast, Float
from sqlalchemy.sql import text
from app.core.logging import logger
from app.db.session import get_db
from app.core.auth import get_current_active_user
from app.models.user import User as UserModel
from app.models.department import Department
from app.models.budget import Budget
from app.models.transaction import Transaction, TransactionType
from app.schemas.report import DashboardData, ReportSummary
from app.services.report import ReportService
from app.core.rbac import can_read_report

router = APIRouter()


@router.get("/", response_model=DashboardData)
async def get_dashboard_data(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(can_read_report),
) -> DashboardData:
    """
    Get dashboard data for visualization.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dashboard data
    """
    logger.info("Getting dashboard data")
    
    # Get total counts
    departments_result = await db.execute(select(func.count(Department.id)))
    total_departments = departments_result.scalar()
    
    budgets_result = await db.execute(select(func.count(Budget.id)))
    total_budgets = budgets_result.scalar()
    
    transactions_result = await db.execute(select(func.count(Transaction.id)))
    total_transactions = transactions_result.scalar()
    
    # Get total budget amount
    budget_amount_result = await db.execute(select(func.sum(Budget.total_amount)))
    total_budget_amount = budget_amount_result.scalar() or Decimal("0.00")
    
    # Get total spent amount
    spent_amount_result = await db.execute(select(func.sum(Budget.spent_amount)))
    total_spent_amount = spent_amount_result.scalar() or Decimal("0.00")
    
    # Calculate budget utilization percentage
    budget_utilization_percent = (
        float(total_spent_amount / total_budget_amount * 100) 
        if total_budget_amount > 0 else 0.0
    )
    
    # Get recent transactions (last 10)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_transactions_result = await db.execute(
        select(Transaction, Budget, Department)
        .join(Budget, Transaction.budget_id == Budget.id)
        .join(Department, Budget.department_id == Department.id)
        .where(Transaction.transaction_date >= thirty_days_ago)
        .order_by(Transaction.transaction_date.desc())
        .limit(10)
    )
    
    recent_transactions = []
    for transaction, budget, department in recent_transactions_result:
        recent_transactions.append({
            "id": transaction.id,
            "description": transaction.description,
            "amount": float(transaction.amount),
            "type": transaction.transaction_type.value,
            "date": transaction.transaction_date.isoformat(),
            "department": department.name,
            "reference_number": transaction.reference_number
        })
    
    # Get top spending departments
    top_spending_result = await db.execute(
        select(
            Department.id,
            Department.name,
            func.sum(Budget.spent_amount).label("total_spent")
        )
        .join(Budget, Department.id == Budget.department_id)
        .group_by(Department.id, Department.name)
        .order_by(func.sum(Budget.spent_amount).desc())
        .limit(5)
    )
    
    top_spending_departments = []
    for dept_id, dept_name, total_spent in top_spending_result:
        top_spending_departments.append({
            "id": dept_id,
            "name": dept_name,
            "total_spent": float(total_spent or 0)
        })
    
    # Get monthly spending trend for the current fiscal year
    current_year = datetime.now().year
    fiscal_year = f"{current_year}-{current_year + 1}"
    
    # Try to get transactions for the current fiscal year
    monthly_trend_result = await db.execute(
        select(
            extract('month', Transaction.transaction_date).label('month'),
            func.sum(
                case(
                    (Transaction.transaction_type == TransactionType.EXPENSE, Transaction.amount),
                    (Transaction.transaction_type == TransactionType.TRANSFER_OUT, Transaction.amount),
                    (Transaction.transaction_type == TransactionType.REFUND, -Transaction.amount),
                    (Transaction.transaction_type == TransactionType.TRANSFER_IN, -Transaction.amount),
                    else_=0
                )
            ).label('amount')
        )
        .join(Budget, Transaction.budget_id == Budget.id)
        .where(
            and_(
                Budget.fiscal_year == fiscal_year,
                extract('year', Transaction.transaction_date) == current_year
            )
        )
        .group_by(extract('month', Transaction.transaction_date))
    )
    
    # Convert result to list to check if it's empty
    monthly_trend_data = monthly_trend_result.all()
    
    # If no transactions found for the fiscal year, get all transactions for the current year
    if not monthly_trend_data:
        logger.info(f"No transactions found for fiscal year {fiscal_year}, getting all transactions for {current_year}")
        monthly_trend_result = await db.execute(
            select(
                extract('month', Transaction.transaction_date).label('month'),
                func.sum(
                    case(
                        (Transaction.transaction_type == TransactionType.EXPENSE, Transaction.amount),
                        (Transaction.transaction_type == TransactionType.TRANSFER_OUT, Transaction.amount),
                        (Transaction.transaction_type == TransactionType.REFUND, -Transaction.amount),
                        (Transaction.transaction_type == TransactionType.TRANSFER_IN, -Transaction.amount),
                        else_=0
                    )
            ).label('amount')
        )
        .join(Budget, Transaction.budget_id == Budget.id)
        .where(extract('year', Transaction.transaction_date) == current_year)
        .group_by(extract('month', Transaction.transaction_date))
    )
        monthly_trend_data = monthly_trend_result.all()
    
    # Initialize all months with 0
    monthly_spending_trend = [{"month": i, "amount": 0.0} for i in range(1, 13)]
    
    # Update with actual data
    for month, amount in monthly_trend_data:
        month_index = int(month) - 1
        if 0 <= month_index < 12:
            monthly_spending_trend[month_index]["amount"] = float(amount or 0)
    
    # Get report summary data with error handling
    report_summary = None
    try:
        report_summary = await ReportService.get_report_summary(db)
    except Exception as e:
        logger.error(f"Error getting report summary: {e}")
        # Create a minimal report summary to avoid breaking the dashboard
        report_summary = ReportSummary(
            total_reports=0,
            reports_by_type={},
            recent_reports=[],
            popular_reports=[]
        )
    
    return DashboardData(
        total_departments=total_departments,
        total_budgets=total_budgets,
        total_transactions=total_transactions,
        total_budget_amount=float(total_budget_amount),
        total_spent_amount=float(total_spent_amount),
        budget_utilization_percent=budget_utilization_percent,
        recent_transactions=recent_transactions,
        top_spending_departments=top_spending_departments,
        monthly_spending_trend=monthly_spending_trend,
        report_summary=report_summary
    )

@router.get("/spending-comparison", response_model=Dict[str, Any])
async def get_spending_comparison(
    period: str = Query("monthly", description="Comparison period (monthly, quarterly, yearly)"),
    years: int = Query(2, description="Number of years to compare"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get year-over-year and month-over-month spending comparisons.
    
    Args:
        period: Comparison period (monthly, quarterly, yearly)
        years: Number of years to compare
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Spending comparison data
    """
    logger.info(f"Getting spending comparison for period: {period}, years: {years}")
    
    current_year = datetime.now().year
    comparison_data = {}
    
    if period == "monthly":
        # Get monthly spending for the specified number of years
        for year_offset in range(years):
            year = current_year - year_offset
            fiscal_year = f"{year}-{year + 1}"
            
            monthly_result = await db.execute(
                select(
                    extract('month', Transaction.transaction_date).label('month'),
                    func.sum(
                        case(
                            (Transaction.transaction_type == TransactionType.EXPENSE, Transaction.amount),
                            (Transaction.transaction_type == TransactionType.TRANSFER_OUT, Transaction.amount),
                            (Transaction.transaction_type == TransactionType.REFUND, -Transaction.amount),
                            (Transaction.transaction_type == TransactionType.TRANSFER_IN, -Transaction.amount),
                            else_=0
                        )
                    ).label('amount')
                )
                .join(Budget, Transaction.budget_id == Budget.id)
                .where(
                    and_(
                        Budget.fiscal_year == fiscal_year,
                        extract('year', Transaction.transaction_date) == year
                    )
                )
                .group_by(extract('month', Transaction.transaction_date))
            )
            
            monthly_data = {f"month_{i}": 0.0 for i in range(1, 13)}
            for month, amount in monthly_result:
                monthly_data[f"month_{int(month)}"] = float(amount or 0)
            
            comparison_data[f"year_{year}"] = monthly_data
    
    elif period == "quarterly":
        # Get quarterly spending for the specified number of years
        for year_offset in range(years):
            year = current_year - year_offset
            fiscal_year = f"{year}-{year + 1}"
            
            quarterly_result = await db.execute(
                select(
                    (
                        func.floor((extract('month', Transaction.transaction_date) - 1) / 3) + 1
                    ).label('quarter'),
                    func.sum(
                        case(
                            (Transaction.transaction_type == TransactionType.EXPENSE, Transaction.amount),
                            (Transaction.transaction_type == TransactionType.TRANSFER_OUT, Transaction.amount),
                            (Transaction.transaction_type == TransactionType.REFUND, -Transaction.amount),
                            (Transaction.transaction_type == TransactionType.TRANSFER_IN, -Transaction.amount),
                            else_=0
                        )
                    ).label('amount')
                )
                .join(Budget, Transaction.budget_id == Budget.id)
                .where(
                    and_(
                        Budget.fiscal_year == fiscal_year,
                        extract('year', Transaction.transaction_date) == year
                    )
                )
                .group_by(
                    func.floor((extract('month', Transaction.transaction_date) - 1) / 3) + 1
                )
            )
            
            quarterly_data = {f"q{i}": 0.0 for i in range(1, 5)}
            for quarter, amount in quarterly_result:
                quarterly_data[f"q{int(quarter)}"] = float(amount or 0)
            
            comparison_data[f"year_{year}"] = quarterly_data
    
    elif period == "yearly":
        # Get yearly spending for the specified number of years
        for year_offset in range(years):
            year = current_year - year_offset
            fiscal_year = f"{year}-{year + 1}"
            
            yearly_result = await db.execute(
                select(
                    func.sum(
                        case(
                            (Transaction.transaction_type == TransactionType.EXPENSE, Transaction.amount),
                            (Transaction.transaction_type == TransactionType.TRANSFER_OUT, Transaction.amount),
                            (Transaction.transaction_type == TransactionType.REFUND, -Transaction.amount),
                            (Transaction.transaction_type == TransactionType.TRANSFER_IN, -Transaction.amount),
                            else_=0
                        )
                    ).label('amount')
                )
                .join(Budget, Transaction.budget_id == Budget.id)
                .where(Budget.fiscal_year == fiscal_year)
            )
            
            amount = yearly_result.scalar() or 0
            comparison_data[f"year_{year}"] = float(amount)
    
    return {
        "period": period,
        "comparison_data": comparison_data,
        "years_compared": years
    }

@router.get("/department-trends", response_model=Dict[str, Any])
async def get_department_trends(
    department_id: str = Query(..., description="Department ID"),
    time_range: int = Query(6, description="Time range in months (3, 6, 12)"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get department spending trends over time.
    
    Args:
        department_id: Department ID
        time_range: Time range in months
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Department spending trends data
    """
    logger.info(f"Getting department trends for department {department_id} over {time_range} months")
    
    # Get department name
    department_result = await db.execute(
        select(Department.name).where(Department.id == department_id)
    )
    department_name = department_result.scalar()
    
    if not department_name:
        return {"error": "Department not found"}
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=time_range * 30)
    
    # Get monthly spending for the department
    trends_result = await db.execute(
        select(
            extract('year', Transaction.transaction_date).label('year'),
            extract('month', Transaction.transaction_date).label('month'),
            func.sum(
                case(
                    (Transaction.transaction_type == TransactionType.EXPENSE, Transaction.amount),
                    (Transaction.transaction_type == TransactionType.TRANSFER_OUT, Transaction.amount),
                    (Transaction.transaction_type == TransactionType.REFUND, -Transaction.amount),
                    (Transaction.transaction_type == TransactionType.TRANSFER_IN, -Transaction.amount),
                    else_=0
                )
            ).label('amount')
        )
        .join(Budget, Transaction.budget_id == Budget.id)
        .where(
            and_(
                Budget.department_id == department_id,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date
            )
        )
        .group_by(
            extract('year', Transaction.transaction_date),
            extract('month', Transaction.transaction_date)
        )
        .order_by(
            extract('year', Transaction.transaction_date),
            extract('month', Transaction.transaction_date)
        )
    )
    
    trends = []
    for year, month, amount in trends_result:
        trends.append({
            "period": f"{year}-{int(month):02d}",
            "amount": float(amount or 0)
        })
    
    return {
        "department_id": department_id,
        "department_name": department_name,
        "time_range_months": time_range,
        "trends": trends
    }

@router.get("/budget-variance", response_model=Dict[str, Any])
async def get_budget_variance(
    department_id: Optional[str] = Query(None, description="Department ID"),
    fiscal_year: str = Query(..., description="Fiscal year"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get budget variance analysis comparing budgeted vs actual spending.
    
    Args:
        department_id: Optional Department ID
        fiscal_year: Fiscal year
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Budget variance analysis data
    """
    logger.info(f"Getting budget variance for fiscal year {fiscal_year}")
    
    # Build query for budgets
    budget_query = select(
        Department.id,
        Department.name,
        Budget.total_amount,
        Budget.spent_amount,
        (Budget.spent_amount / Budget.total_amount * 100).label("utilization_percent"),
        (Budget.total_amount - Budget.spent_amount).label("variance_amount"),
        ((Budget.total_amount - Budget.spent_amount) / Budget.total_amount * 100).label("variance_percent")
    ).join(Department, Budget.department_id == Department.id).where(Budget.fiscal_year == fiscal_year)
    
    if department_id:
        budget_query = budget_query.where(Department.id == department_id)
    
    variance_result = await db.execute(budget_query)
    
    variance_data = []
    total_budget = Decimal("0.00")
    total_spent = Decimal("0.00")
    
    for dept_id, dept_name, total_amount, spent_amount, utilization_percent, variance_amount, variance_percent in variance_result:
        variance_data.append({
            "department_id": dept_id,
            "department_name": dept_name,
            "total_budget": float(total_amount or 0),
            "spent_amount": float(spent_amount or 0),
            "utilization_percent": float(utilization_percent or 0),
            "variance_amount": float(variance_amount or 0),
            "variance_percent": float(variance_percent or 0),
            "status": "over_budget" if variance_amount < 0 else "under_budget"
        })
        
        total_budget += total_amount or 0
        total_spent += spent_amount or 0
    
    return {
        "fiscal_year": fiscal_year,
        "department_id": department_id,
        "variance_data": variance_data,
        "summary": {
            "total_budget": float(total_budget),
            "total_spent": float(total_spent),
            "total_variance": float(total_budget - total_spent),
            "total_variance_percent": float((total_budget - total_spent) / total_budget * 100) if total_budget > 0 else 0
        }
    }

@router.get("/spending-forecast", response_model=Dict[str, Any])
async def get_spending_forecast(
    forecast_period: int = Query(3, description="Forecast period in months (1, 3, 6)"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get spending forecast based on historical trends.
    
    Args:
        forecast_period: Forecast period in months
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Spending forecast data
    """
    logger.info(f"Getting spending forecast for {forecast_period} months")
    
    # Get historical spending data for the last 12 months
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    historical_result = await db.execute(
        select(
            extract('month', Transaction.transaction_date).label('month'),
            extract('year', Transaction.transaction_date).label('year'),
            func.sum(
                case(
                    (Transaction.transaction_type == TransactionType.EXPENSE, Transaction.amount),
                    (Transaction.transaction_type == TransactionType.TRANSFER_OUT, Transaction.amount),
                    (Transaction.transaction_type == TransactionType.REFUND, -Transaction.amount),
                    (Transaction.transaction_type == TransactionType.TRANSFER_IN, -Transaction.amount),
                    else_=0
                )
            ).label('amount')
        )
        .join(Budget, Transaction.budget_id == Budget.id)
        .where(
            and_(
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date
            )
        )
        .group_by(
            extract('year', Transaction.transaction_date),
            extract('month', Transaction.transaction_date)
        )
        .order_by(
            extract('year', Transaction.transaction_date),
            extract('month', Transaction.transaction_date)
        )
    )
    
    # Calculate average monthly spending
    monthly_totals = {}
    for year, month, amount in historical_result:
        key = f"{year}-{int(month):02d}"
        monthly_totals[key] = float(amount or 0)
    
    # Simple moving average forecast
    avg_monthly_spending = sum(monthly_totals.values()) / len(monthly_totals) if monthly_totals else 0
    
    # Generate forecast
    forecast = []
    current_date = datetime.now()
    
    for i in range(1, forecast_period + 1):
        forecast_date = current_date + timedelta(days=30 * i)
        forecast_month = forecast_date.month
        forecast_year = forecast_date.year
        
        # Apply seasonal adjustment (simple: increase by 5% each month)
        seasonal_factor = 1 + (0.05 * i)
        forecast_amount = avg_monthly_spending * seasonal_factor
        
        forecast.append({
            "period": f"{forecast_year}-{forecast_month:02d}",
            "forecast_amount": round(forecast_amount, 2),
            "confidence": "medium"  # Simple confidence level
        })
    
    return {
        "forecast_period_months": forecast_period,
        "historical_average": round(avg_monthly_spending, 2),
        "forecast": forecast
    }

@router.get("/anomalies", response_model=Dict[str, Any])
async def get_spending_anomalies(
    threshold: float = Query(2.0, description="Sensitivity threshold (1.0-3.0)"),
    time_range: int = Query(30, description="Time range in days"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Identify unusual spending patterns or outliers.
    
    Args:
        threshold: Sensitivity level
        time_range: Time range in days
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Anomaly detection results
    """
    logger.info(f"Getting spending anomalies with threshold {threshold} over {time_range} days")
    
    # Get transaction data for the specified time range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=time_range)
    
    transactions_result = await db.execute(
        select(
            Transaction.id,
            Transaction.description,
            Transaction.amount,
            Transaction.transaction_type,
            Transaction.transaction_date,
            Department.name.label("department_name")
        )
        .join(Budget, Transaction.budget_id == Budget.id)
        .join(Department, Budget.department_id == Department.id)
        .where(Transaction.transaction_date >= start_date)
        .order_by(Transaction.transaction_date.desc())
    )
    
    transactions = []
    for transaction_id, description, amount, transaction_type, transaction_date, department_name in transactions_result:
        transactions.append({
            "id": transaction_id,
            "description": description,
            "amount": float(amount),
            "type": transaction_type.value,
            "date": transaction_date.isoformat(),
            "department": department_name
        })
    
    # Calculate average transaction amount
    if transactions:
        amounts = [t["amount"] for t in transactions if t["type"] in ["expense", "transfer_out"]]
        avg_amount = sum(amounts) / len(amounts) if amounts else 0
        
        # Identify anomalies (transactions significantly above average)
        anomalies = []
        for transaction in transactions:
            if transaction["type"] in ["expense", "transfer_out"]:
                if transaction["amount"] > avg_amount * threshold:
                    anomalies.append({
                        "transaction": transaction,
                        "deviation": round((transaction["amount"] - avg_amount) / avg_amount, 2),
                        "severity": "high" if transaction["amount"] > avg_amount * threshold * 1.5 else "medium"
                    })
        
        return {
            "threshold": threshold,
            "time_range_days": time_range,
            "average_transaction_amount": round(avg_amount, 2),
            "total_transactions": len(transactions),
            "anomalies_count": len(anomalies),
            "anomalies": anomalies
        }
    
    return {
        "threshold": threshold,
        "time_range_days": time_range,
        "average_transaction_amount": 0,
        "total_transactions": 0,
        "anomalies_count": 0,
        "anomalies": []
    }

# In your app/routers/dashboard.py file

@router.get("/custom-range", response_model=Dict[str, Any])
async def get_custom_range_data(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    metrics: List[str] = Query(["departments", "budgets", "transactions", "utilization"], description="Metrics to include"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get dashboard data for a custom date range.
    
    Args:
        start_date: Start date
        end_date: End date
        metrics: List of metrics to include
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Custom range dashboard data
    """
    logger.info(f"Getting custom range data from {start_date} to {end_date}")
    
    result = {}
    
    if "departments" in metrics:
        departments_result = await db.execute(
            select(func.count(Department.id))
        )
        result["departments_count"] = departments_result.scalar()
    
    if "budgets" in metrics:
        budgets_result = await db.execute(
            select(
                func.count(Budget.id),
                func.sum(Budget.total_amount),
                func.sum(Budget.spent_amount)
            )
        )
        count, total_budget, total_spent = budgets_result.first()
        result["budgets_count"] = count
        result["total_budget_amount"] = float(total_budget or 0)
        result["total_spent_amount"] = float(total_spent or 0)
    
    if "transactions" in metrics:
        transactions_result = await db.execute(
            select(
                func.count(Transaction.id),
                func.sum(
                    case(
                        (Transaction.transaction_type == TransactionType.EXPENSE, Transaction.amount),
                        (Transaction.transaction_type == TransactionType.TRANSFER_OUT, Transaction.amount),
                        (Transaction.transaction_type == TransactionType.REFUND, -Transaction.amount),
                        (Transaction.transaction_type == TransactionType.TRANSFER_IN, -Transaction.amount),
                        else_=0
                    )
                )
            )
            .join(Budget, Transaction.budget_id == Budget.id)
            .where(
                and_(
                    Transaction.transaction_date >= start_date,
                    Transaction.transaction_date <= end_date
                )
            )
        )
        count, total_amount = transactions_result.first()
        result["transactions_count"] = count
        result["transactions_amount"] = float(total_amount or 0)
    
    if "utilization" in metrics:
        utilization_result = await db.execute(
            select(
                Department.id,
                Department.name,
                Budget.total_amount,
                Budget.spent_amount,
                (Budget.spent_amount / Budget.total_amount * 100).label("utilization_percent")
            )
            .join(Budget, Budget.department_id == Department.id)
            .where(
                and_(
                    Budget.fiscal_year == f"{start_date.year}-{start_date.year + 1}",
                    Budget.created_at <= end_date
                )
            )
        )
        
        utilization_data = []
        for dept_id, dept_name, total_amount, spent_amount, utilization_percent in utilization_result:
            utilization_data.append({
                "department_id": dept_id,
                "department_name": dept_name,
                "total_budget": float(total_amount or 0),
                "spent_amount": float(spent_amount or 0),
                "utilization_percent": float(utilization_percent or 0)
            })
        
        result["utilization"] = utilization_data
    
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "metrics": metrics,
        "data": result
    }

@router.get("/transaction-analysis", response_model=Dict[str, Any])
async def get_transaction_analysis(
    category: Optional[str] = Query(None, description="Transaction category (expense, refund, transfer_in, transfer_out)"),
    time_range: int = Query(30, description="Time range in days"),
    min_amount: Optional[float] = Query(None, description="Minimum transaction amount"),
    max_amount: Optional[float] = Query(None, description="Maximum transaction amount"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get detailed transaction analysis and insights.
    
    Args:
        category: Transaction category filter
        time_range: Time range in days
        min_amount: Minimum transaction amount
        max_amount: Maximum transaction amount
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Transaction analysis data
    """
    logger.info(f"Getting transaction analysis for category: {category}")
    
    # Build query with filters
    end_date = datetime.now()
    start_date = end_date - timedelta(days=time_range)
    
    query = select(
        Transaction.id,
        Transaction.description,
        Transaction.amount,
        Transaction.transaction_type,
        Transaction.transaction_date,
        Department.name.label("department_name")
    ).join(Budget, Transaction.budget_id == Budget.id).join(
        Department, Budget.department_id == Department.id
    ).where(
        Transaction.transaction_date >= start_date
    )
    
    if category:
        query = query.where(Transaction.transaction_type == category)
    
    if min_amount:
        query = query.where(Transaction.amount >= min_amount)
    
    if max_amount:
        query = query.where(Transaction.amount <= max_amount)
    
    transactions_result = await db.execute(query.order_by(Transaction.transaction_date.desc()))
    
    transactions = []
    total_amount = 0
    daily_totals = {}
    
    for transaction_id, description, amount, transaction_type, transaction_date, department_name in transactions_result:
        transactions.append({
            "id": transaction_id,
            "description": description,
            "amount": float(amount),
            "type": transaction_type.value,
            "date": transaction_date.isoformat(),
            "department": department_name
        })
        
        total_amount += amount
        
        # Aggregate by day
        day_key = transaction_date.strftime("%Y-%m-%d")
        if day_key not in daily_totals:
            daily_totals[day_key] = 0
        daily_totals[day_key] += amount
    
    # Calculate statistics
    avg_transaction = total_amount / len(transactions) if transactions else 0
    max_transaction = max([t["amount"] for t in transactions]) if transactions else 0
    min_transaction = min([t["amount"] for t in transactions]) if transactions else 0
    
    # Find peak spending day
    peak_day = max(daily_totals.items(), key=lambda x: x[1]) if daily_totals else (None, 0)
    
    return {
        "category": category,
        "time_range_days": time_range,
        "min_amount": min_amount,
        "max_amount": max_amount,
        "total_transactions": len(transactions),
        "total_amount": round(total_amount, 2),
        "average_transaction": round(avg_transaction, 2),
        "max_transaction": round(max_transaction, 2),
        "min_transaction": round(min_transaction, 2),
        "peak_spending_day": {
            "date": peak_day[0],
            "amount": round(peak_day[1], 2)
        },
        "daily_totals": {k: round(v, 2) for k, v in daily_totals.items()}
    }

@router.get("/department-distribution", response_model=List[Dict[str, Any]])
async def get_department_distribution(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """
    Get department spending distribution for pie chart visualization.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Department distribution data
    """
    logger.info("Getting department distribution")
    
    # Get spending by department
    distribution_result = await db.execute(
        select(
            Department.id,
            Department.name,
            func.sum(Budget.spent_amount).label("total_spent")
        )
        .join(Budget, Department.id == Budget.department_id)
        .group_by(Department.id, Department.name)
        .order_by(func.sum(Budget.spent_amount).desc())
    )
    
    distribution = []
    for dept_id, dept_name, total_spent in distribution_result:
        distribution.append({
            "id": dept_id,
            "name": dept_name,
            "value": float(total_spent or 0)
        })
    
    return distribution

@router.get("/monthly-spending-trend", response_model=List[Dict[str, Any]])
async def get_monthly_spending_trend(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """
    Get monthly spending trend for line chart visualization.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Monthly spending trend data
    """
    logger.info("Getting monthly spending trend")
    
    current_year = datetime.now().year
    fiscal_year = f"{current_year}-{current_year + 1}"
    
    # Try to get transactions for the current fiscal year
    monthly_trend_result = await db.execute(
        select(
            extract('month', Transaction.transaction_date).label('month'),
            func.sum(
                case(
                    (Transaction.transaction_type == TransactionType.EXPENSE, Transaction.amount),
                    (Transaction.transaction_type == TransactionType.TRANSFER_OUT, Transaction.amount),
                    (Transaction.transaction_type == TransactionType.REFUND, -Transaction.amount),
                    (Transaction.transaction_type == TransactionType.TRANSFER_IN, -Transaction.amount),
                    else_=0
                )
            ).label('amount')
        )
        .join(Budget, Transaction.budget_id == Budget.id)
        .where(
            and_(
                Budget.fiscal_year == fiscal_year,
                extract('year', Transaction.transaction_date) == current_year
            )
        )
        .group_by(extract('month', Transaction.transaction_date))
    )
    
    # Convert result to list to check if it's empty
    monthly_trend_data = monthly_trend_result.all()
    
    # If no transactions found for the fiscal year, get all transactions for the current year
    if not monthly_trend_data:
        logger.info(f"No transactions found for fiscal year {fiscal_year}, getting all transactions for {current_year}")
        monthly_trend_result = await db.execute(
            select(
                extract('month', Transaction.transaction_date).label('month'),
                func.sum(
                    case(
                        (Transaction.transaction_type == TransactionType.EXPENSE, Transaction.amount),
                        (Transaction.transaction_type == TransactionType.TRANSFER_OUT, Transaction.amount),
                        (Transaction.transaction_type == TransactionType.REFUND, -Transaction.amount),
                        (Transaction.transaction_type == TransactionType.TRANSFER_IN, -Transaction.amount),
                        else_=0
                    )
                ).label('amount')
            )
            .join(Budget, Transaction.budget_id == Budget.id)
            .where(extract('year', Transaction.transaction_date) == current_year)
            .group_by(extract('month', Transaction.transaction_date))
        )
        monthly_trend_data = monthly_trend_result.all()
    
    # Initialize all months with 0
    monthly_spending_trend = [{"name": f"{i}", "value": 0.0} for i in range(1, 13)]
    
    # Update with actual data
    for month, amount in monthly_trend_data:
        month_index = int(month) - 1
        if 0 <= month_index < 12:
            monthly_spending_trend[month_index]["value"] = float(amount or 0)
    
    return monthly_spending_trend

# In your app/routers/dashboard.py file

@router.get("/budget-utilization", response_model=List[Dict[str, Any]])
async def get_budget_utilization(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """
    Get budget utilization data for bar chart visualization.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Budget utilization data
    """
    logger.info("Getting budget utilization")
    
    current_year = datetime.now().year
    fiscal_year = f"{current_year}-{current_year + 1}"
    
    # Try to get budgets for the current fiscal year first
    utilization_result = await db.execute(
        select(
            Department.id,
            Department.name,
            Budget.total_amount,
            Budget.spent_amount,
            (Budget.spent_amount / Budget.total_amount * 100).label("utilization_percent")
        )
        .join(Budget, Department.id == Budget.department_id)
        .where(Budget.fiscal_year == fiscal_year)
    )
    
    # Convert result to list to check if it's empty
    utilization_data = utilization_result.all()
    
    # If no budgets found for the fiscal year, get all budgets
    if not utilization_data:
        logger.info(f"No budgets found for fiscal year {fiscal_year}, getting all budgets")
        utilization_result = await db.execute(
            select(
                Department.id,
                Department.name,
                Budget.total_amount,
                Budget.spent_amount,
                (Budget.spent_amount / Budget.total_amount * 100).label("utilization_percent")
            )
            .join(Budget, Department.id == Budget.department_id)
        )
        utilization_data = utilization_result.all()
    
    utilization = []
    for dept_id, dept_name, total_amount, spent_amount, utilization_percent in utilization_data:
        utilization.append({
            "id": dept_id,
            "name": dept_name,
            "value": float(utilization_percent or 0),
            "total_budget": float(total_amount or 0),
            "spent_amount": float(spent_amount or 0)
        })
    
    return utilization

@router.get("/transaction-types", response_model=List[Dict[str, Any]])
async def get_transaction_types(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """
    Get transaction type distribution for pie chart visualization.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Transaction type distribution data
    """
    logger.info("Getting transaction types")
    
    # Get transaction counts by type
    transaction_types_result = await db.execute(
        select(
            Transaction.transaction_type,
            func.count(Transaction.id).label("count"),
            func.sum(Transaction.amount).label("total_amount")
        )
        .group_by(Transaction.transaction_type)
    )
    
    transaction_types = []
    for transaction_type, count, total_amount in transaction_types_result:
        transaction_types.append({
            "name": transaction_type.value,
            "value": float(total_amount or 0),
            "count": count
        })
    
    return transaction_types