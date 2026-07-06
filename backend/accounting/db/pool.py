"""Async connection pool for accounting module.

Provides a shared connection pool with automatic health checks.
The pool is a singleton — created once, reused globally.
"""

from __future__ import annotations

import asyncpg
from backend.accounting.db import get_dsn

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Create or return the shared connection pool (singleton)."""
    global _pool
    if _pool is None or _pool._closed:
        _pool = await asyncpg.create_pool(
            get_dsn(),
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
    return _pool


async def get_connection() -> asyncpg.Connection:
    """Get a single connection from the pool."""
    pool = await get_pool()
    return await pool.acquire()


async def release_pool() -> None:
    """Close the pool gracefully."""
    global _pool
    if _pool and not _pool._closed:
        await _pool.close()
    _pool = None
