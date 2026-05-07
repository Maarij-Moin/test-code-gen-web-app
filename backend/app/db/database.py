"""Production async database configuration for SQLAlchemy 2.0."""

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

DEFAULT_SQLITE_URL = "sqlite+aiosqlite:///./app.db"


def _resolve_database_url() -> str:
    url = settings.DATABASE_URL.strip()
    if url.startswith("sqlite"):
        return url
    logger.warning("Non-SQLite DATABASE_URL detected. Falling back to SQLite.")
    return DEFAULT_SQLITE_URL


DATABASE_URL = _resolve_database_url()

engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    poolclass=NullPool,
    connect_args={"check_same_thread": False},
)

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
    """Ensure auth tables exist for SQLite deployments."""

    from app.models.user_model import AuthBase

    async with engine.begin() as conn:
        await conn.run_sync(AuthBase.metadata.create_all)


async def dispose_engine() -> None:
    """Dispose database connections during graceful shutdown."""

    await engine.dispose()
