"""
Database configuration and session management
Uses SQLAlchemy with async support
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator
import logging

from .config import settings

logger = logging.getLogger(__name__)

# Determine if we're using SQLite
is_sqlite = settings.database_url_async.startswith("sqlite")

# Create async engine with conditional parameters
if is_sqlite:
    # SQLite doesn't support connection pooling parameters
    engine = create_async_engine(
        settings.database_url_async,
        echo=settings.DATABASE_ECHO,
        poolclass=NullPool,
    )
else:
    # PostgreSQL and other databases support pooling
    engine = create_async_engine(
        settings.database_url_async,
        echo=settings.DATABASE_ECHO,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_pre_ping=True,  # Verify connections before use
        poolclass=None if settings.ENVIRONMENT != "test" else NullPool,
    )

# Create sync engine for background tasks
if is_sqlite:
    # SQLite sync engine
    sync_engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        poolclass=NullPool,
    )
else:
    # PostgreSQL and other databases
    sync_engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_pre_ping=True,
        poolclass=None if settings.ENVIRONMENT != "test" else NullPool,
    )

# Create session factories
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

SessionLocal = sessionmaker(
    sync_engine,
    autocommit=False,
    autoflush=False,
)

# Create declarative base
Base = declarative_base()

# Database dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Create and yield database session
    Ensures proper cleanup after use
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

def get_db_sync() -> Generator[Session, None, None]:
    """
    Create and yield synchronous database session for background tasks
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

@contextmanager
def get_db_sync_context() -> Generator[Session, None, None]:
    """
    Context manager for synchronous database sessions
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions
    Useful for scripts and background tasks
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db() -> None:
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")

async def close_db() -> None:
    """Close database connections"""
    await engine.dispose()
    logger.info("Database connections closed")
