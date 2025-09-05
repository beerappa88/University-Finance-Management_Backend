"""
Logging configuration for the application.

This module sets up logging with different levels for different environments.
It uses loguru for more advanced logging capabilities.
"""

import sys
from typing import Dict, Any

from loguru import logger

from .config import settings


def setup_logging() -> None:
    """Set up logging configuration based on the environment."""
    
    # Remove default logger
    logger.remove()
    
    # Define log format
    log_format = (
        "{time:YYYY-MM-DD HH:mm:ss} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{message}"
    )
    
    # Configure logger based on environment
    if settings.environment == "production":
        # Production logging - more structured, less verbose
        logger.add(
            sys.stdout,
            format=log_format,
            level=settings.log_level,
            colorize=False,
            serialize=True,
        )
    else:
        # Development/Testing logging - more verbose, colored
        logger.add(
            sys.stdout,
            format=log_format,
            level=settings.log_level,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )
    
    logger.info(f"Logging initialized for environment: {settings.environment}")


# Initialize logging
setup_logging()