"""
Main application entry point.

This module initializes the FastAPI application and includes all routers.
"""

from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import logger
from app.core.middleware import (
    SecurityHeadersMiddleware,
    PermissionContextMiddleware,
    AuditMiddleware
    # RateLimitMiddleware
)
# from app.core.rbac import ROLE_RATE_LIMITS
from app.routers.departments import router as departments_router
from app.routers.budgets import router as budgets_router
from app.routers.transactions import router as transactions_router
from app.routers.health import router as health_router
from app.routers.auth import router as auth_router
from app.routers.reports import router as reports_router
from app.routers.dashboard import router as dashboard_router
from app.routers.users import router as users_router
from app.routers.exports import router as exports_router
from app.routers.auth_2fa import router as auth_2fa_router
from app.routers.notifications import router as notifications_router
from app.routers.sessions import router as sessions_router
from app.routers.account import router as account_router
from app.routers.audit import router as audit_router
from app.db.audit import setup_audit_event_listeners
from app.core.auth import get_current_active_user


app = FastAPI(
    title=settings.api.title,
    description=settings.api.description,
    version=settings.api.version,
    debug=settings.debug,
)

# Add middleware in the correct order
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(PermissionContextMiddleware)
app.add_middleware(AuditMiddleware)
# app.add_middleware(RateLimitMiddleware, rate_limits=ROLE_RATE_LIMITS)

# Add CORS middleware - Updated to be more restrictive
origins = settings.frontend_urls

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include routers with /api prefix
app.include_router(
    health_router,
    prefix="/api/health",
    tags=["health"],
)
app.include_router(
    auth_router,
    prefix="/api/auth",
    tags=["authentication"],
)
app.include_router(
    auth_2fa_router,
    prefix="/api/auth/2fa",
    tags=["authentication-2fa"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    notifications_router,
    prefix="/api/notifications",
    tags=["notifications"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    sessions_router,
    prefix="/api/auth/sessions",
    tags=["sessions"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    account_router,
    prefix="/api/account",
    tags=["account"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    users_router,
    prefix="/api/users",
    tags=["users"],
)
app.include_router(
    departments_router,
    prefix="/api/departments",
    tags=["departments"],
)
app.include_router(
    budgets_router,
    prefix="/api/budgets",
    tags=["budgets"],
)
app.include_router(
    transactions_router,
    prefix="/api/transactions",
    tags=["transactions"],
)
app.include_router(
    reports_router,
    prefix="/api/reports",
    tags=["reports"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    dashboard_router,
    prefix="/api/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    exports_router,
    prefix="/api/exports",
    tags=["exports"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    audit_router,
    prefix="/api/audit-logs",
    tags=["audit-logs"],
    dependencies=[Depends(get_current_active_user)],
)

setup_audit_event_listeners()

# @app.on_event("startup")
# async def startup_event():
#     """Actions to run on application startup."""
#     logger.info("Starting University Finance Management API")
#     logger.info(f"Environment: {settings.environment}")
#     logger.info(f"Debug mode: {settings.debug}")
#     logger.info(f"Database URL: {settings.database.url[:20]}...")
#     logger.info(f"Redis Host: {settings.redis.host}:{settings.redis.port}")

@app.on_event("startup")
async def startup_event():
    """Actions to run on application startup."""
    logger.info("Starting University Finance Management API")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Database URL: {settings.database.url[:20]}...")

    # === Redis Initialization ===
    from app.core.cache import redis_client, check_redis_connection

    if redis_client is None:
        logger.warning("Redis is disabled due to configuration or initialization failure.")
    else:
        try:
            if await check_redis_connection():
                logger.info("Redis connection established successfully")
                # Optionally log DB size or ping latency
                db_size = await redis_client.dbsize()
                logger.debug(f"Redis DB size: {db_size} keys")
            else:
                logger.error("Failed to connect to Redis. Caching will be disabled.")
                # Optionally disable cache globally here if critical
        except Exception as e:
            logger.error(f"Unexpected error during Redis connection check: {e}")

    # === Audit Setup ===
    setup_audit_event_listeners()

    # === Final App Info ===
    logger.info(f"API Docs available at: http://{settings.api.host}:{settings.api.port}/docs")

@app.on_event("shutdown")
async def shutdown_event():
    """Actions to run on application shutdown."""
    logger.info("Shutting down University Finance Management API")

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "University Finance Management API",
        "version": settings.api.version,
        "docs": "/docs",
    }