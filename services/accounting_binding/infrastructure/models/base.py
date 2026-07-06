"""
SQLAlchemy Base — engine + session factory.

Forward-only: upgrade(), no downgrade().
Rollback через новую миграцию + rebuild projection.
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config.settings import settings


class Base(DeclarativeBase):
    """Базовый класс для ORM-моделей."""
    pass


engine = None
async_session_factory = None


def init_engine(db_url: str | None = None) -> None:
    """Инициализировать engine (lazy — не на импорте)."""
    global engine, async_session_factory
    url = db_url or settings.DATABASE_URL or "sqlite+aiosqlite:///./data/accounting_binding.db"
    _engine = create_async_engine(url, echo=False, pool_size=5, max_overflow=10)
    engine = _engine
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False,
    )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """DI: сессия для FastAPI (требует init_engine())."""
    if async_session_factory is None:
        init_engine()
    async with async_session_factory() as session:  # type: ignore
        yield session
