"""Database connection for the accounting module.

Uses direct asyncpg (not SQLAlchemy) per project pattern.
DSN sourced exclusively from backend.config.settings.DATABASE_URL.
"""
from __future__ import annotations

from functools import lru_cache

from backend.config import settings


@lru_cache(maxsize=1)
def get_dsn() -> str:
    """Return the sync DSN (asyncpg prefix removed)."""
    return settings.DATABASE_URL.replace("+asyncpg", "")
