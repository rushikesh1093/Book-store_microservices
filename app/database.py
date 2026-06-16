"""
app/database.py

Database wiring for the Analytics microservice.

We connect to the SAME PostgreSQL database as the Django backend (read-only for
the business tables: books, orders, order_items, users, ...) and additionally
own a small set of analytics tables (events / report metadata) which live in
the same database under the ``analytics_*`` prefix.

Two engines are provided:
  * async engine  -> used by the FastAPI request path (routers / services)
  * sync engine   -> used by pandas + report generation (read_sql) and the
                     APScheduler jobs which run outside the async loop.
"""
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

logger = logging.getLogger("analytics.database")


class Base(DeclarativeBase):
    """Declarative base for analytics-owned tables."""


# ── Async engine (request path) ────────────────────────────────
async_engine = create_async_engine(
    settings.async_database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# ── Sync engine (pandas / reports / scheduler) ─────────────────
sync_engine = create_engine(
    settings.sync_database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=5,
)

SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)


# ── FastAPI dependency ─────────────────────────────────────────
async def get_db() -> AsyncSession:
    """Yield an async session for request handlers."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_models() -> None:
    """Create analytics-owned tables if they do not yet exist."""
    # Import models so they register on Base.metadata.
    from app.models import events  # noqa: F401

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Analytics tables ensured.")


async def check_database() -> bool:
    """Lightweight connectivity probe used by /health."""
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Database health check failed: %s", exc)
        return False
