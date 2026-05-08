"""Production async database configuration for SQLAlchemy 2.0.

Supports both PostgreSQL (production via Docker) and SQLite (local dev fallback).
The driver is auto-detected from DATABASE_URL:
  - postgresql+asyncpg://...  → PostgreSQL with connection pool
  - sqlite+aiosqlite:///...   → SQLite (NullPool, check_same_thread=False)
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine configuration
# ---------------------------------------------------------------------------

DATABASE_URL: str = settings.DATABASE_URL.strip()

_is_sqlite = DATABASE_URL.startswith("sqlite")

_engine_kwargs: dict = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
}

if _is_sqlite:
    # SQLite requires NullPool and check_same_thread=False for async
    _engine_kwargs["poolclass"] = NullPool
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    logger.info("Using SQLite database: %s", DATABASE_URL)
else:
    # PostgreSQL — use a bounded connection pool (5 idle, burst to 20)
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 15
    _engine_kwargs["pool_recycle"] = 1800  # recycle connections after 30 min
    logger.info("Using PostgreSQL database")


engine: AsyncEngine = create_async_engine(DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a transaction-capable async session."""

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except SQLAlchemyError:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_auth_db() -> None:
    """Create all tables from AuthBase metadata (idempotent)."""

    from app.models.user_model import AuthBase

    async with engine.begin() as conn:
        await conn.run_sync(AuthBase.metadata.create_all)

    logger.info("Database tables initialized.")


async def dispose_engine() -> None:
    """Dispose database connections during graceful shutdown."""

    await engine.dispose()
