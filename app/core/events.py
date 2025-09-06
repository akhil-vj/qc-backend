"""
Application lifecycle events
Handles startup and shutdown tasks
"""

from fastapi import FastAPI
import logging
from contextlib import asynccontextmanager

from .database import init_db, close_db
from .cache import cache
from .logging import setup_logging
from .config import settings

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup and shutdown events
    """
    # Startup
    try:
        # Setup logging
        setup_logging()
        logger.info("Starting QuickCart API...")
        
        # Initialize database
        if settings.ENVIRONMENT != "test":
            await init_db()
            logger.info("Database initialized")
        
        # Connect to Redis
        await cache.connect()
        logger.info("Cache connected")
        
        # Initialize other services
        # TODO: Add Sentry, monitoring, etc.
        
        logger.info("QuickCart API started successfully")
        
        yield
        
    finally:
        # Shutdown
        logger.info("Shutting down QuickCart API...")
        
        # Close database connections
        await close_db()
        logger.info("Database connections closed")
        
        # Disconnect from Redis
        await cache.disconnect()
        logger.info("Cache disconnected")
        
        logger.info("QuickCart API shutdown complete")

async def create_startup_data():
    """Create initial data on startup"""
    # This would be called from a separate script
    # Example: Create default categories, admin user, etc.
    pass
