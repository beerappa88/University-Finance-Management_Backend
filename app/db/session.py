"""
Database session management.

This module provides utilities for creating and managing database sessions
using async SQLAlchemy with PostgreSQL.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.logging import logger
# from app.models import (
#     Base,
#     Department,
#     Budget,
#     Transaction,
#     User,
#     AuditLog,
#     Report
# )

# Create async engine
engine = create_async_engine(
    settings.database.url,  # Use the property
    echo=settings.debug,
    future=True,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    pool_pre_ping=True,
    pool_recycle=settings.database.pool_recycle,
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session.
    
    This function is used as a dependency in FastAPI endpoints to provide
    a database session. It ensures the session is properly closed after use.
    
    Yields:
        AsyncSession: Database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()