"""
Routers package initialization.

This module imports all routers to make them available from a single import point.
"""

from app.routers.departments import router as departments_router
from app.routers.budgets import router as budgets_router
from app.routers.transactions import router as transactions_router
from app.routers.health import router as health_router
from app.routers.auth import router as auth_router
from app.routers.dashboard import router as dashboard_router
from app.routers.users import router as users_router
from app.routers.exports import router as exports_router
from app.routers.reports import router as reports_router
from app.routers.auth_2fa import router as auth_2fa_router
from app.routers.notifications import router as notifications_router
from app.routers.sessions import router as sessions_router
from app.routers.account import router as account_router

__all__ = [
    "departments_router", 
    "budgets_router", 
    "transactions_router", 
    "health_router", 
    "auth_router", 
    "dashboard_router", 
    "users_router",
    "exports_router",
    "reports_router",
    "auth_2fa_router",
    "notifications_router",
    "sessions_router",
    "account_router"
]