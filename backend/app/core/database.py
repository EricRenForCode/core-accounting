"""Async SQLAlchemy engine, session factories, and FastAPI dependency injection.

Lazy-initialized engines: configured at application startup via configure().
Provides:
- Primary async engine (read/write) for business operations
- AI read-only async engine (SELECT only, statement_timeout=5s, no DML)
- get_db() — FastAPI dependency for primary DB session
- get_ai_readonly_db() — FastAPI dependency for AI query path
"""

from typing import AsyncGenerator, Optional

import sqlalchemy as sa
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings

__all__ = [
    "configure",
    "get_db",
    "get_ai_readonly_db",
]

# ── Module-level stored references (lazy) ────────────────────
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
_ai_readonly_engine: Optional[AsyncEngine] = None
_ai_readonly_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
_configured: bool = False


def configure(settings: Optional[Settings] = None) -> None:
    """Initialize database engines with actual configuration.

    Must be called once at application startup before any DB access.
    Idempotent — subsequent calls are no-ops.
    """
    global _engine, _session_factory, _ai_readonly_engine, _ai_readonly_session_factory, _configured

    if _configured:
        return

    if settings is None:
        settings = Settings()

    # ── Primary Engine (read/write) ──────────────────────────
    _engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        echo=settings.DEBUG,
    )
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # ── AI Read-Only Engine ──────────────────────────────────
    _ai_readonly_engine = create_async_engine(
        settings.AI_READONLY_DATABASE_URL,
        pool_size=5,
        max_overflow=5,
        pool_timeout=10,
        pool_recycle=1800,
        echo=False,
    )

    @event.listens_for(_ai_readonly_engine.sync_engine, "connect")
    def _set_ai_readonly_params(dbapi_connection, connection_record):
        """Set statement_timeout=5s + read-only for AI queries."""
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("SET statement_timeout = 5000")
            cursor.execute("SET default_transaction_read_only = on")
        finally:
            cursor.close()

    _ai_readonly_session_factory = async_sessionmaker(
        _ai_readonly_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    _configured = True


async def dispose() -> None:
    """Dispose all connection pools. Called at application shutdown."""
    global _engine, _ai_readonly_engine, _configured
    if _engine:
        await _engine.dispose()
    if _ai_readonly_engine:
        await _ai_readonly_engine.dispose()
    _configured = False


def _check_configured() -> None:
    """Raise RuntimeError if configure() hasn't been called."""
    if not _configured:
        raise RuntimeError(
            "Database not configured. Call db.configure(settings) at startup."
        )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a primary (read/write) database session."""
    _check_configured()
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_ai_readonly_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an AI read-only database session.

    This connection uses statement_timeout=5s and read-only mode.
    Used exclusively for /ai/query and NL→SQL paths (§3.12, §4).
    """
    _check_configured()
    async with _ai_readonly_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
