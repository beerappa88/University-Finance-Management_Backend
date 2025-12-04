"""
Pydantic schemas for reports.

This module defines the request and response schemas for report-related
API endpoints using Pydantic models.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ReportBase(BaseModel):
    """Base schema for report data."""
    
    name: str
    report_type: str
    parameters: Dict[str, Any]


class ReportCreate(ReportBase):
    """Schema for creating a new report."""
    
    pass


class ReportUpdate(BaseModel):
    """Schema for updating an existing report."""

    name: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class Report(ReportBase):
    """Schema for report response data."""
    
    id: UUID
    results: Optional[Dict[str, Any]] = None
    generated_by: UUID
    generated_at: datetime
    
    class Config:
        """Configuration for the Report schema."""
        
        from_attribute = True


class ReportFilter(BaseModel):
    """Schema for filtering reports."""

    report_type: Optional[str] = None
    generated_by: Optional[UUID] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    search: Optional[str] = None


class ReportSummary(BaseModel):
    """Schema for report summary data."""

    total_reports: int
    reports_by_type: Dict[str, int]
    recent_reports: List[Dict[str, Any]]
    popular_reports: List[Dict[str, Any]]


class DashboardData(BaseModel):
    """Schema for dashboard data."""
    
    total_departments: int
    total_budgets: int
    total_transactions: int
    total_budget_amount: float
    total_spent_amount: float
    budget_utilization_percent: float
    recent_transactions: list
    top_spending_departments: list
    monthly_spending_trend: list
    report_summary: Optional[ReportSummary] = None