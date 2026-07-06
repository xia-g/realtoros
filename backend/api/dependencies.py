"""FastAPI dependency injection container.

Provides database sessions, current user context, and other
shared dependencies used across route handlers.
"""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import async_session_factory
from backend.core.context import get_request_context

security_scheme = HTTPBearer(auto_error=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session per request.

    Yields a session that is committed on success or rolled back on error.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> str | None:
    """Resolve the current authenticated user ID.

    Currently returns a stub. Will integrate with JWT in a future sprint.
    """
    ctx = get_request_context()
    if ctx and ctx.user_id:
        return ctx.user_id

    if credentials:
        # Stub: decode JWT here in future sprint
        return "stub-user-id"

    return None
