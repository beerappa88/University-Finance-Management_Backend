"""
Main entry point for running the application with `python -m app`.
"""
import uvicorn
from app.main import app
from app.core.config import settings
from app.core.logging import logger

def main():
    """Run the application with uvicorn."""
    logger.info(f"Starting {settings.api.title} on {settings.host}:{settings.port}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Log level: {settings.logging.level}")
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.logging.level.lower(),
        access_log=True,
        workers=1 if settings.debug else None
    )

if __name__ == "__main__":
    main()
