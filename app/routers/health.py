"""
Health check endpoints.

This module provides endpoints for checking the health of the application,
including database connectivity.
"""

from typing import Dict

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.logging import logger
from app.db.session import get_db

router = APIRouter()


@router.get("/", response_model=Dict[str, str])
async def health_check() -> Dict[str, str]:
    """
    Basic health check endpoint.
    
    Returns:
        Health status
    """
    logger.debug("Health check endpoint called")
    return {"status": "ok"}


@router.get("/db", response_model=Dict[str, str])
async def database_health_check(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Database health check endpoint.
    
    Args:
        db: Database session
        
    Returns:
        Database health status
    """
    logger.debug("Database health check endpoint called")
    
    try:
        # Execute a simple query to check database connectivity
        result = await db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            logger.debug("Database health check successful")
            return {"status": "ok", "database": "connected"}
        else:
            logger.error("Database health check failed - unexpected result")
            return {"status": "error", "database": "unexpected_result"}
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return {"status": "error", "database": f"connection_error: {str(e)}"}