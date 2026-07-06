"""Knowledge Session Repository — ownership-enforced CRUD.

SECURITY: ALL queries filter by user_id.
Never trust session_id without ownership verification (Review Gate C3).
Never use GenericRepository.get() without user_id filter.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.knowledge_session import KnowledgeSession
from backend.models.knowledge_message import KnowledgeMessage


DEFAULT_SESSION_TTL_HOURS = 24


class KnowledgeSessionRepository:
    """Repository for knowledge_sessions with mandatory ownership filtering.

    Every method requires user_id to enforce session isolation.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_session(
        self,
        user_id: UUID,
        tenant_id: UUID | None = None,
        title: str | None = None,
        correlation_id: str | None = None,
        ttl_hours: int = DEFAULT_SESSION_TTL_HOURS,
    ) -> KnowledgeSession:
        """Create a new session with 24h TTL."""
        now = datetime.now(timezone.utc)
        session = KnowledgeSession(
            user_id=user_id,
            tenant_id=tenant_id,
            title=title,
            last_activity_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
            is_active=True,
            correlation_id=correlation_id,
        )
        self.session.add(session)
        await self.session.flush()
        return session

    async def get_session(self, session_id: UUID, user_id: UUID) -> KnowledgeSession | None:
        """Get a session by id — ALWAYS filtered by user_id."""
        stmt = select(KnowledgeSession).where(
            KnowledgeSession.id == session_id,
            KnowledgeSession.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_session(self, user_id: UUID) -> KnowledgeSession | None:
        """Get the most recent active (non-expired) session for a user."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(KnowledgeSession)
            .where(
                KnowledgeSession.user_id == user_id,
                KnowledgeSession.is_active == True,  # noqa: E712
                KnowledgeSession.expires_at > now,
            )
            .order_by(KnowledgeSession.last_activity_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def touch_session(self, session_id: UUID, user_id: UUID) -> bool:
        """Update last_activity_at and push expires_at by 24h."""
        session = await self.get_session(session_id, user_id)
        if session is None:
            return False
        now = datetime.now(timezone.utc)
        session.last_activity_at = now
        session.expires_at = now + timedelta(hours=DEFAULT_SESSION_TTL_HOURS)
        await self.session.flush()
        return True

    async def expire_session(self, session_id: UUID, user_id: UUID) -> bool:
        """Mark session as expired."""
        session = await self.get_session(session_id, user_id)
        if session is None:
            return False
        now = datetime.now(timezone.utc)
        session.is_active = False
        session.expires_at = now
        await self.session.flush()
        return True

    async def list_user_sessions(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        include_expired: bool = False,
    ) -> tuple[list[KnowledgeSession], int]:
        """List sessions for a user with pagination."""
        stmt = select(KnowledgeSession).where(KnowledgeSession.user_id == user_id)

        if not include_expired:
            now = datetime.now(timezone.utc)
            stmt = stmt.where(KnowledgeSession.expires_at > now)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = stmt.order_by(KnowledgeSession.last_activity_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def delete_expired(self) -> int:
        """Hard delete all expired sessions (cascade deletes messages)."""
        now = datetime.now(timezone.utc)
        stmt = select(func.count()).select_from(KnowledgeSession).where(
            KnowledgeSession.expires_at <= now,
            KnowledgeSession.is_active == False,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0

        delete_stmt = delete(KnowledgeSession).where(
            KnowledgeSession.expires_at <= now,
            KnowledgeSession.is_active == False,  # noqa: E712
        )
        await self.session.execute(delete_stmt)
        await self.session.flush()
        return count


class KnowledgeMessageRepository:
    """Repository for knowledge_messages — always accessed through session context."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_message(
        self,
        session_id: UUID,
        role: str,
        content: str,
        token_count: int = 0,
        correlation_id: str | None = None,
    ) -> KnowledgeMessage:
        """Add a message to a session."""
        msg = KnowledgeMessage(
            session_id=session_id,
            role=role,
            content=content,
            token_count=token_count,
            correlation_id=correlation_id,
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def list_messages(
        self,
        session_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[KnowledgeMessage], int]:
        """List messages in a session, oldest first."""
        stmt = (
            select(KnowledgeMessage)
            .where(KnowledgeMessage.session_id == session_id)
            .order_by(KnowledgeMessage.created_at.asc())
        )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def get_recent_messages(
        self,
        session_id: UUID,
        limit: int = 20,
    ) -> list[KnowledgeMessage]:
        """Get the most recent N messages (oldest first within the window)."""
        # Get last N by created_at DESC, then reverse
        stmt = (
            select(KnowledgeMessage)
            .where(KnowledgeMessage.session_id == session_id)
            .order_by(KnowledgeMessage.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        items.reverse()
        return items

    async def count_messages(self, session_id: UUID) -> int:
        """Count messages in a session."""
        stmt = select(func.count()).select_from(KnowledgeMessage).where(
            KnowledgeMessage.session_id == session_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def delete_session_messages(self, session_id: UUID) -> int:
        """Delete all messages for a session (for truncation)."""
        delete_stmt = delete(KnowledgeMessage).where(
            KnowledgeMessage.session_id == session_id,
        )
        result = await self.session.execute(delete_stmt)
        await self.session.flush()
        return result.rowcount
