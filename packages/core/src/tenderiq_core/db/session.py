"""Async SQLAlchemy engine ve session fabrikaları."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tenderiq_core.config import Settings, get_settings


def create_engine(settings: Settings | None = None) -> AsyncEngine:
    """Ayarlardaki ``DATABASE_URL`` ile bir async engine üretir."""
    resolved = settings or get_settings()
    return create_async_engine(
        resolved.database_url,
        pool_pre_ping=True,
        future=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Verilen engine için bir async session fabrikası üretir."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
