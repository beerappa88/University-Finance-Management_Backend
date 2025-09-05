"""
Service layer for financial reports.

This module contains the business logic for generating financial reports
and dashboard data.
"""

from app.core.logging import logger
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, extract, case, desc

# from app.core.logging import logger
from app.models.department import Department
from app.models.budget import Budget
from app.models.transaction import Transaction, TransactionType
from app.models.report import Report
from app.schemas.report import ReportCreate, ReportUpdate, ReportSummary, ReportFilter
from app.core.cache import get_cache, set_cache, get_cache
from uuid import UUID

class ReportService:
    """Service class for financial reports."""
    
    @staticmethod
    async def generate_budget_vs_actual_report(
        db: AsyncSession,
        fiscal_year: str,
        department_id: Optional[UUID] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a budget vs actual spending report with caching.
        
        Args:
            db: Database session
            fiscal_year: Fiscal year to report on
            department_id: Optional department ID to filter by
            use_cache: Whether to use caching
            
        Returns:
            Report data
        """
        # Create cache key
        cache_key = f"budget_vs_actual:{fiscal_year}:{department_id or 'all'}"

        # Try to get from cache
        if use_cache:
            cached_data = await get_cache(cache_key)
            if cached_data:
                # from app.core.logging import logger
                logger.info(f"Cache hit for {cache_key}")
                return cached_data
        
        
        logger.info(f"Generating budget vs actual report for {fiscal_year}")
        
        # Build query for budgets
        budget_query = select(Budget).where(Budget.fiscal_year == fiscal_year)
        if department_id:
            budget_query = budget_query.where(Budget.department_id == department_id)
        
        result = await db.execute(budget_query)
        budgets = result.scalars().all()
        
        report_data = {
            "fiscal_year": fiscal_year,
            "generated_at": datetime.now().isoformat(),
            "departments": []
        }
        
        total_budget = Decimal("0.00")
        total_spent = Decimal("0.00")
        
        for budget in budgets:
            # Get all transactions for this budget
            transaction_result = await db.execute(
                select(Transaction).where(Transaction.budget_id == budget.id)
            )
            transactions = transaction_result.scalars().all()
            
            # Calculate total spent
            spent = Decimal("0.00")
            for transaction in transactions:
                if transaction.transaction_type in [TransactionType.EXPENSE, TransactionType.TRANSFER_OUT]:
                    spent += transaction.amount
                elif transaction.transaction_type in [TransactionType.REFUND, TransactionType.TRANSFER_IN]:
                    spent -= transaction.amount
            
            # Get department name
            dept_result = await db.execute(
                select(Department).where(Department.id == budget.department_id)
            )
            department = dept_result.scalars().first()
            
            department_data = {
                "department_id": budget.department_id,
                "department_name": department.name if department else "Unknown",
                "budget_id": budget.id,
                "total_budget": float(budget.total_amount),
                "total_spent": float(spent),
                "remaining": float(budget.remaining_amount),
                "utilization_percent": round(float(spent / budget.total_amount * 100), 2) if budget.total_amount > 0 else 0
            }
            
            report_data["departments"].append(department_data)
            
            total_budget += budget.total_amount
            total_spent += spent
        
        # Add summary
        report_data["summary"] = {
            "total_budget": float(total_budget),
            "total_spent": float(total_spent),
            "total_remaining": float(total_budget - total_spent),
            "overall_utilization_percent": round(float(total_spent / total_budget * 100), 2) if total_budget > 0 else 0
        }

        if use_cache:
            await set_cache(cache_key, report_data, expire=timedelta(minutes=30))
        
        return report_data
    
    @staticmethod
    async def generate_department_spending_report(
        db: AsyncSession,
        start_date: date,
        end_date: date,
        department_id: Optional[UUID] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a department spending report with caching.
        
        Args:
            db: Database session
            start_date: Start date for the report
            end_date: End date for the report
            department_id: Optional department ID to filter by
            use_cache: Whether to use caching
            
        Returns:
            Report data
        """
        # Create cache key
        cache_key = f"department_spending:{start_date}:{end_date}:{department_id or 'all'}"

        # Try to get from cache
        if use_cache:
            cached_data = await get_cache(cache_key)
            if cached_data:
                # from app.core.logging import logger
                logger.info(f"Cache hit for {cache_key}")
                return cached_data
        
        
        logger.info(f"Generating department spending report from {start_date} to {end_date}")
        
        # Build query for transactions
        transaction_query = select(
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
            transaction_query = transaction_query.where(Budget.department_id == department_id)
        
        result = await db.execute(transaction_query)
        results = result.all()
        
        # Group by department
        department_spending = {}
        
        for transaction, budget, department in results:
            dept_id = department.id
            dept_name = department.name
            
            if dept_id not in department_spending:
                department_spending[dept_id] = {
                    "department_id": dept_id,
                    "department_name": dept_name,
                    "expenses": Decimal("0.00"),
                    "refunds": Decimal("0.00"),
                    "transfers_in": Decimal("0.00"),
                    "transfers_out": Decimal("0.00"),
                    "net_spending": Decimal("0.00"),
                    "transaction_count": 0
                }
            
            dept_data = department_spending[dept_id]
            dept_data["transaction_count"] += 1
            
            if transaction.transaction_type == TransactionType.EXPENSE:
                dept_data["expenses"] += transaction.amount
                dept_data["net_spending"] += transaction.amount
            elif transaction.transaction_type == TransactionType.REFUND:
                dept_data["refunds"] += transaction.amount
                dept_data["net_spending"] -= transaction.amount
            elif transaction.transaction_type == TransactionType.TRANSFER_IN:
                dept_data["transfers_in"] += transaction.amount
                dept_data["net_spending"] -= transaction.amount
            elif transaction.transaction_type == TransactionType.TRANSFER_OUT:
                dept_data["transfers_out"] += transaction.amount
                dept_data["net_spending"] += transaction.amount
        
        # Convert to list and calculate totals
        departments = list(department_spending.values())
        
        total_expenses = sum(d["expenses"] for d in departments)
        total_refunds = sum(d["refunds"] for d in departments)
        total_transfers_in = sum(d["transfers_in"] for d in departments)
        total_transfers_out = sum(d["transfers_out"] for d in departments)
        total_net_spending = sum(d["net_spending"] for d in departments)
        total_transactions = sum(d["transaction_count"] for d in departments)
        
        # Convert Decimal to float for JSON serialization
        for dept in departments:
            dept["expenses"] = float(dept["expenses"])
            dept["refunds"] = float(dept["refunds"])
            dept["transfers_in"] = float(dept["transfers_in"])
            dept["transfers_out"] = float(dept["transfers_out"])
            dept["net_spending"] = float(dept["net_spending"])
        
        report_data = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "generated_at": datetime.now().isoformat(),
            "departments": departments,
            "summary": {
                "total_expenses": float(total_expenses),
                "total_refunds": float(total_refunds),
                "total_transfers_in": float(total_transfers_in),
                "total_transfers_out": float(total_transfers_out),
                "total_net_spending": float(total_net_spending),
                "total_transactions": total_transactions
            }
        }

        if use_cache:
            await set_cache(cache_key, report_data, expire=timedelta(minutes=30))

        
        return report_data
    
    @staticmethod
    async def generate_monthly_spending_trend(
        db: AsyncSession,
        fiscal_year: str,
        department_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Generate a monthly spending trend report.
        
        Args:
            db: Database session
            fiscal_year: Fiscal year to report on
            department_id: Optional department ID to filter by
            
        Returns:
            Report data
        """
        logger.info(f"Generating monthly spending trend for {fiscal_year}")
        
        # Build query for transactions by month
        transaction_query = select(
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
        ).join(
            Budget, Transaction.budget_id == Budget.id
        ).where(
            Budget.fiscal_year == fiscal_year
        ).group_by(
            extract('month', Transaction.transaction_date)
        )
        
        if department_id:
            transaction_query = transaction_query.where(Budget.department_id == department_id)
        
        result = await db.execute(transaction_query)
        monthly_data = result.all()
        
        # Convert to dictionary
        monthly_spending = {int(month): float(amount) for month, amount in monthly_data}
        
        # Fill in missing months with 0
        all_months = {i: 0.0 for i in range(1, 13)}
        all_months.update(monthly_spending)
        
        report_data = {
            "fiscal_year": fiscal_year,
            "generated_at": datetime.now().isoformat(),
            "monthly_spending": all_months,
            "total_spending": sum(all_months.values())
        }
        
        return report_data
    
    @staticmethod
    async def save_report(
        db: AsyncSession,
        report_in: ReportCreate,
        results: Dict[str, Any],
        user_id: UUID
    ) -> Report:
        logger.info(f"Saving report: {report_in.name}")
        
        def convert_uuids_to_strings(obj):
            """Recursively convert UUID objects to strings in nested structures."""
            if isinstance(obj, UUID):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: convert_uuids_to_strings(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_uuids_to_strings(item) for item in obj]
            elif isinstance(obj, tuple):
                return tuple(convert_uuids_to_strings(item) for item in obj)
            elif hasattr(obj, '__dict__'):  # Handle objects with attributes
                return convert_uuids_to_strings(obj.__dict__)
            else:
                return obj
        
        # Create deep copies and convert UUIDs to strings
        parameters = convert_uuids_to_strings(report_in.parameters)
        results = convert_uuids_to_strings(results)
        
        report = Report(
            name=report_in.name,
            report_type=report_in.report_type,
            parameters=parameters,
            results=results,
            generated_by=user_id
        )
        
        db.add(report)
        await db.commit()
        await db.refresh(report)
        
        return report
    
    @staticmethod
    async def get_saved_reports(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> List[Report]:
        """
        Get all saved reports.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of reports
        """
        logger.debug(f"Getting saved reports, skip={skip}, limit={limit}")
        
        result = await db.execute(
            select(Report).offset(skip).limit(limit).order_by(Report.generated_at.desc())
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_report_by_id(
        db: AsyncSession,
        report_id: UUID
    ) -> Optional[Report]:
        """
        Get a report by ID.
        
        Args:
            db: Database session
            report_id: Report ID
            
        Returns:
            Report if found, None otherwise
        """
        logger.debug(f"Getting report by ID: {report_id}")
        
        result = await db.execute(
            select(Report).where(Report.id == report_id)
        )
        return result.scalars().first()
    

    @staticmethod
    async def get_reports_with_filter(
        db: AsyncSession,
        filters: ReportFilter,
        skip: int = 0,
        limit: int = 100
    ) -> List[Report]:
        """
        Get reports with filtering capabilities.
        """
        query = select(Report)
        
        if filters.report_type:
            query = query.where(Report.report_type == filters.report_type)
        
        if filters.generated_by:
            query = query.where(Report.generated_by == filters.generated_by)
        
        if filters.start_date:
            query = query.where(Report.generated_at >= filters.start_date)
        
        if filters.end_date:
            query = query.where(Report.generated_at <= filters.end_date)
        
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.where(or_(
                Report.name.ilike(search_term),
                Report.report_type.ilike(search_term)
            ))
        
        query = query.offset(skip).limit(limit).order_by(desc(Report.generated_at))
        
        result = await db.execute(query)
        return result.scalars().all()


    @staticmethod
    async def get_report_summary(db: AsyncSession) -> ReportSummary:
        """
        Get a summary of reports statistics.
        """
        # Total reports count
        total_result = await db.execute(select(func.count(Report.id)))
        total_reports = total_result.scalar()
        
        # Reports by type
        type_result = await db.execute(
            select(Report.report_type, func.count(Report.id).label('count'))
            .group_by(Report.report_type)
        )
        reports_by_type = {row.report_type: row.count for row in type_result.all()}
        
        # Recent reports (last 5)
        recent_result = await db.execute(
            select(Report)
            .order_by(desc(Report.generated_at))
            .limit(5)
        )
        recent_reports = recent_result.scalars().all()
        
        # Convert SQLAlchemy models to dictionaries
        recent_reports_dicts = []
        for report in recent_reports:
            recent_reports_dicts.append({
                "id": report.id,
                "name": report.name,
                "report_type": report.report_type,
                "parameters": report.parameters,
                "results": report.results,
                "generated_by": report.generated_by,
                "generated_at": report.generated_at
            })
        
        # Popular reports (most generated types)
        popular_result = await db.execute(
            select(Report.report_type, func.count(Report.id).label('count'))
            .group_by(Report.report_type)
            .order_by(desc('count'))
            .limit(3)
        )
        popular_reports_rows = popular_result.all()
        
        # Convert Row objects to dictionaries
        popular_reports_dicts = []
        for row in popular_reports_rows:
            popular_reports_dicts.append({
                "report_type": row.report_type,
                "count": row.count
            })
        
        return ReportSummary(
            total_reports=total_reports,
            reports_by_type=reports_by_type,
            recent_reports=recent_reports_dicts,
            popular_reports=popular_reports_dicts
        )

    @staticmethod
    async def update_report(
        db: AsyncSession,
        report_id: UUID,
        report_update: ReportUpdate
    ) -> Optional[Report]:
        """
        Update a report's name or parameters.
        """
        result = await db.execute(select(Report).where(Report.id == report_id))
        report = result.scalars().first()
        
        if not report:
            return None
        
        if report_update.name is not None:
            report.name = report_update.name
        
        if report_update.parameters is not None:
            report.parameters = report_update.parameters
        
        await db.commit()
        await db.refresh(report)
        
        return report

    @staticmethod
    async def get_report_statistics(
        db: AsyncSession,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get report generation statistics for the last N days.
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Reports generated in the period
        result = await db.execute(
            select(func.count(Report.id))
            .where(and_(
                Report.generated_at >= start_date,
                Report.generated_at <= end_date
            ))
        )
        total_generated = result.scalar()
        
        # Reports by type in the period
        type_result = await db.execute(
            select(Report.report_type, func.count(Report.id).label('count'))
            .where(and_(
                Report.generated_at >= start_date,
                Report.generated_at <= end_date
            ))
            .group_by(Report.report_type)
        )
        by_type = {row.report_type: row.count for row in type_result.all()}
        
        # Daily generation trend
        daily_result = await db.execute(
            select(
                func.date(Report.generated_at).label('date'),
                func.count(Report.id).label('count')
            )
            .where(and_(
                Report.generated_at >= start_date,
                Report.generated_at <= end_date
            ))
            .group_by(func.date(Report.generated_at))
            .order_by('date')
        )
        daily_trend = [
            {"date": row.date.strftime('%Y-%m-%d'), "count": row.count}
            for row in daily_result.all()
        ]
        
        return {
            "period_days": days,
            "total_generated": total_generated,
            "by_type": by_type,
            "daily_trend": daily_trend
        }

    @staticmethod
    async def cleanup_old_reports(
        db: AsyncSession,
        days: int = 90
    ) -> int:
        """
        Delete reports older than specified days.
        Returns the number of deleted reports.
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        result = await db.execute(
            select(Report)
            .where(Report.generated_at < cutoff_date)
        )
        old_reports = result.scalars().all()
        
        count = len(old_reports)
        
        for report in old_reports:
            await db.delete(report)
        
        await db.commit()
        
        return count
    
    @staticmethod
    async def generate_expense_categories_report(
        db: AsyncSession,
        start_date: date,
        end_date: date,
        department_id: Optional[UUID] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Generate an expense categories report with caching.
        
        Args:
            db: Database session
            start_date: Start date for the report
            end_date: End date for the report
            department_id: Optional department ID to filter by
            use_cache: Whether to use caching
            
        Returns:
            Report data
        """
        # Create cache key
        cache_key = f"expense_categories:{start_date}:{end_date}:{department_id or 'all'}"
        
        # Try to get from cache
        if use_cache:
            cached_data = await get_cache(cache_key)
            if cached_data:
                logger.info(f"Cache hit for {cache_key}")
                return cached_data
        
        logger.info(f"Generating expense categories report from {start_date} to {end_date}")
        
        # Build query for transactions by category
        transaction_query = select(
            Transaction.category,
            func.sum(Transaction.amount).label('total_amount'),
            func.count(Transaction.id).label('transaction_count')
        ).join(
            Budget, Transaction.budget_id == Budget.id
        ).where(
            and_(
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
                Transaction.transaction_type == TransactionType.EXPENSE
            )
        ).group_by(
            Transaction.category
        )
        
        if department_id:
            transaction_query = transaction_query.where(Budget.department_id == department_id)
        
        result = await db.execute(transaction_query)
        category_data = result.all()
        
        # Convert to list of dictionaries
        categories = [
            {
                "category": row.category or "Uncategorized",
                "total_amount": float(row.total_amount),
                "transaction_count": row.transaction_count
            }
            for row in category_data
        ]
        
        # Calculate totals
        total_amount = sum(cat["total_amount"] for cat in categories)
        total_transactions = sum(cat["transaction_count"] for cat in categories)
        
        # Prepare chart data
        chart_data = {
            "labels": [cat["category"] for cat in categories],
            "datasets": [
                {
                    "label": "Expense Amount",
                    "data": [cat["total_amount"] for cat in categories],
                    "backgroundColor": [
                        'rgba(255, 99, 132, 0.8)',
                        'rgba(54, 162, 235, 0.8)',
                        'rgba(255, 206, 86, 0.8)',
                        'rgba(75, 192, 192, 0.8)',
                        'rgba(153, 102, 255, 0.8)',
                        'rgba(255, 159, 64, 0.8)'
                    ],
                    "borderColor": [
                        'rgb(255, 99, 132)',
                        'rgb(54, 162, 235)',
                        'rgb(255, 206, 86)',
                        'rgb(75, 192, 192)',
                        'rgb(153, 102, 255)',
                        'rgb(255, 159, 64)'
                    ],
                    "borderWidth": 1
                }
            ]
        }
        
        # Prepare table data
        table_data = {
            "headers": ["Category", "Amount", "Transaction Count", "Percentage"],
            "rows": [
                [
                    cat["category"],
                    f"${cat['total_amount']:.2f}",
                    cat["transaction_count"],
                    f"{(cat['total_amount'] / total_amount * 100):.1f}%"
                ]
                for cat in categories
            ]
        }
        
        report_data = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "generated_at": datetime.now().isoformat(),
            "categories": categories,
            "summary": {
                "total_amount": float(total_amount),
                "total_transactions": total_transactions,
                "category_count": len(categories)
            },
            "chartData": chart_data,
            "tableData": table_data
        }
        
        if use_cache:
            await set_cache(cache_key, report_data, expire=timedelta(minutes=30))
        
        return report_data

    @staticmethod
    async def generate_revenue_vs_expenses_report(
        db: AsyncSession,
        start_date: date,
        end_date: date,
        department_id: Optional[UUID] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a revenue vs expenses report with caching.
        
        Args:
            db: Database session
            start_date: Start date for the report
            end_date: End date for the report
            department_id: Optional department ID to filter by
            use_cache: Whether to use caching
            
        Returns:
            Report data
        """
        # Create cache key
        cache_key = f"revenue_vs_expenses:{start_date}:{end_date}:{department_id or 'all'}"
        
        # Try to get from cache
        if use_cache:
            cached_data = await get_cache(cache_key)
            if cached_data:
                logger.info(f"Cache hit for {cache_key}")
                return cached_data
        
        logger.info(f"Generating revenue vs expenses report from {start_date} to {end_date}")
        
        # Build query for monthly revenue and expenses
        monthly_query = select(
            extract('year', Transaction.transaction_date).label('year'),
            extract('month', Transaction.transaction_date).label('month'),
            func.sum(
                case(
                    (Transaction.transaction_type == TransactionType.REVENUE, Transaction.amount),
                    else_=0
                )
            ).label('revenue'),
            func.sum(
                case(
                    (Transaction.transaction_type == TransactionType.EXPENSE, Transaction.amount),
                    else_=0
                )
            ).label('expenses')
        ).join(
            Budget, Transaction.budget_id == Budget.id
        ).where(
            and_(
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date
            )
        ).group_by(
            extract('year', Transaction.transaction_date),
            extract('month', Transaction.transaction_date)
        ).order_by(
            extract('year', Transaction.transaction_date),
            extract('month', Transaction.transaction_date)
        )
        
        if department_id:
            monthly_query = monthly_query.where(Budget.department_id == department_id)
        
        result = await db.execute(monthly_query)
        monthly_data = result.all()
        
        # Convert to list of dictionaries
        monthly = [
            {
                "year": int(row.year),
                "month": int(row.month),
                "month_name": date(int(row.year), int(row.month), 1).strftime('%b %Y'),
                "revenue": float(row.revenue or 0),
                "expenses": float(row.expenses or 0),
                "net": float((row.revenue or 0) - (row.expenses or 0))
            }
            for row in monthly_data
        ]
        
        # Calculate totals
        total_revenue = sum(m["revenue"] for m in monthly)
        total_expenses = sum(m["expenses"] for m in monthly)
        total_net = total_revenue - total_expenses
        
        # Prepare chart data
        chart_data = {
            "labels": [m["month_name"] for m in monthly],
            "datasets": [
                {
                    "label": "Revenue",
                    "data": [m["revenue"] for m in monthly],
                    "backgroundColor": 'rgba(75, 192, 192, 0.6)',
                    "borderColor": 'rgb(75, 192, 192)',
                    "borderWidth": 2
                },
                {
                    "label": "Expenses",
                    "data": [m["expenses"] for m in monthly],
                    "backgroundColor": 'rgba(255, 99, 132, 0.6)',
                    "borderColor": 'rgb(255, 99, 132)',
                    "borderWidth": 2
                },
                {
                    "label": "Net",
                    "data": [m["net"] for m in monthly],
                    "backgroundColor": 'rgba(153, 102, 255, 0.6)',
                    "borderColor": 'rgb(153, 102, 255)',
                    "borderWidth": 2
                }
            ]
        }
        
        # Prepare table data
        table_data = {
            "headers": ["Month", "Revenue", "Expenses", "Net"],
            "rows": [
                [
                    m["month_name"],
                    f"${m['revenue']:.2f}",
                    f"${m['expenses']:.2f}",
                    f"${m['net']:.2f}"
                ]
                for m in monthly
            ]
        }
        
        report_data = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "generated_at": datetime.now().isoformat(),
            "monthly": monthly,
            "summary": {
                "total_revenue": float(total_revenue),
                "total_expenses": float(total_expenses),
                "total_net": float(total_net),
                "net_margin": (total_net / total_revenue * 100) if total_revenue > 0 else 0
            },
            "chartData": chart_data,
            "tableData": table_data
        }
        
        if use_cache:
            await set_cache(cache_key, report_data, expire=timedelta(minutes=30))
        
        return report_data
    
    @staticmethod
    async def delete_report(
        db: AsyncSession,
        report_id: UUID
    ) -> bool:
        """
        Delete a report by ID.
        
        Args:
            db: Database session
            report_id: Report ID to delete
            
        Returns:
            True if report was deleted, False if not found
        """
        logger.debug(f"Deleting report: {report_id}")
        
        result = await db.execute(select(Report).where(Report.id == report_id))
        report = result.scalars().first()
        
        if not report:
            return False
        
        await db.delete(report)
        await db.commit()
        
        return True
