"""Knowledge Memory Service — session and message management.

SECURITY: All operations enforce user_id ownership.
Never trust session_id without user_id verification.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from backend.core.logging import get_logger
from backend.models.knowledge_session import KnowledgeSession, KnowledgeMessage
from backend.repositories.knowledge_session_repository import (
    KnowledgeSessionRepository,
    KnowledgeMessageRepository,
)
from backend.services.knowledge.memory.contracts import (
    MemoryContext, MemoryMessage, MemorySessionSummary,
)
from backend.ai.metrics import (
    knowledge_sessions_active, knowledge_messages_total,
    knowledge_memory_tokens_total, knowledge_session_expired_total,
    knowledge_memory_truncation_total,
)

logger = get_logger("knowledge")

MAX_TURNS = 10  # 10 user + 10 assistant = 20 messages per ADR-0015 D6
SESSION_TTL_HOURS = 24


class MemoryService:
    """Conversational memory service — session management + message history.

    Independent from Knowledge Graph and Embeddings.
    Memory contributes context; never changes graph data.
    """

    def __init__(self, session):
        self._session = session
        self.session_repo = KnowledgeSessionRepository(session)
        self.message_repo = KnowledgeMessageRepository(session)

    # ── Session Management ──

    async def create_session(
        self,
        user_id: UUID,
        tenant_id: UUID | None = None,
        title: str | None = None,
        correlation_id: str | None = None,
    ) -> MemorySessionSummary:
        """Create a new memory session."""
        sess = await self.session_repo.create_session(
            user_id=user_id,
            tenant_id=tenant_id,
            title=title,
            correlation_id=correlation_id,
        )
        knowledge_sessions_active.inc()

        logger.info(
            "knowledge.session.created",
            user_id=str(user_id),
            session_id=str(sess.id),
            correlation_id=correlation_id,
        )

        return self._to_summary(sess, 0)

    async def get_or_create_session(
        self,
        user_id: UUID,
        tenant_id: UUID | None = None,
        title: str | None = None,
        correlation_id: str | None = None,
    ) -> MemorySessionSummary:
        """Get the active session for a user, or create a new one."""
        active = await self.session_repo.get_active_session(user_id)
        if active is not None:
            await self.session_repo.touch_session(active.id, user_id)
            msg_count = await self.message_repo.count_messages(active.id)
            return self._to_summary(active, msg_count)

        # No active session — create new
        return await self.create_session(
            user_id=user_id,
            tenant_id=tenant_id,
            title=title,
            correlation_id=correlation_id,
        )

    async def get_session(self, session_id: UUID, user_id: UUID) -> MemorySessionSummary | None:
        """Get a session by id with ownership check."""
        sess = await self.session_repo.get_session(session_id, user_id)
        if sess is None:
            return None
        msg_count = await self.message_repo.count_messages(sess.id)
        return self._to_summary(sess, msg_count)

    async def expire_session(self, session_id: UUID, user_id: UUID) -> bool:
        """Manually expire a session."""
        result = await self.session_repo.expire_session(session_id, user_id)
        if result:
            knowledge_sessions_active.dec()
            knowledge_session_expired_total.inc()
            logger.info(
                "knowledge.session.expired",
                session_id=str(session_id),
                user_id=str(user_id),
            )
        return result

    async def list_sessions(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        include_expired: bool = False,
    ) -> tuple[list[MemorySessionSummary], int]:
        """List sessions for a user."""
        sessions, total = await self.session_repo.list_user_sessions(
            user_id=user_id,
            page=page,
            page_size=page_size,
            include_expired=include_expired,
        )
        summaries = []
        for sess in sessions:
            msg_count = await self.message_repo.count_messages(sess.id)
            summaries.append(self._to_summary(sess, msg_count))
        return summaries, total

    # ── Message Management ──

    async def append_user_message(
        self,
        session_id: UUID,
        user_id: UUID,
        content: str,
        token_count: int = 0,
        correlation_id: str | None = None,
    ) -> bool:
        """Append a user message to a session. Enforces ownership."""
        sess = await self.session_repo.get_session(session_id, user_id)
        if sess is None:
            return False

        msg = await self.message_repo.add_message(
            session_id=session_id,
            role="user",
            content=content,
            token_count=token_count,
            correlation_id=correlation_id,
        )
        await self.session_repo.touch_session(session_id, user_id)

        knowledge_messages_total.inc()
        knowledge_memory_tokens_total.inc(token_count)

        logger.info(
            "knowledge.message.added",
            session_id=str(session_id),
            user_id=str(user_id),
            role="user",
            token_count=token_count,
            correlation_id=correlation_id,
        )

        # Enforce max turns — truncate if exceeded
        await self._enforce_max_turns(session_id)
        return True

    async def append_assistant_message(
        self,
        session_id: UUID,
        user_id: UUID,
        content: str,
        token_count: int = 0,
        correlation_id: str | None = None,
    ) -> bool:
        """Append an assistant message. Enforces ownership."""
        sess = await self.session_repo.get_session(session_id, user_id)
        if sess is None:
            return False

        msg = await self.message_repo.add_message(
            session_id=session_id,
            role="assistant",
            content=content,
            token_count=token_count,
            correlation_id=correlation_id,
        )

        knowledge_messages_total.inc()
        knowledge_memory_tokens_total.inc(token_count)

        logger.info(
            "knowledge.message.added",
            session_id=str(session_id),
            user_id=str(user_id),
            role="assistant",
            token_count=token_count,
            correlation_id=correlation_id,
        )

        return True

    async def get_context(
        self,
        session_id: UUID,
        user_id: UUID,
        max_turns: int = MAX_TURNS,
    ) -> MemoryContext:
        """Get the last N turns of conversation context.

        Returns messages oldest → newest (for Context Builder).
        If session is expired, returns is_expired=True with empty messages.
        """
        sess = await self.session_repo.get_session(session_id, user_id)
        if sess is None:
            return MemoryContext(session_id=session_id, is_expired=True)

        # Check expiry
        now = datetime.now(timezone.utc)
        if sess.expires_at <= now:
            knowledge_session_expired_total.inc()
            return MemoryContext(session_id=session_id, is_expired=True)

        # Get recent messages (max_turns * 2 = user + assistant pairs)
        messages = await self.message_repo.get_recent_messages(
            session_id, limit=max_turns * 2,
        )

        memory_messages = [
            MemoryMessage(
                role=m.role,
                content=m.content,
                token_count=m.token_count,
                created_at=m.created_at,
                correlation_id=str(m.correlation_id) if m.correlation_id else None,
            )
            for m in messages
        ]

        total_turns = len(memory_messages) // 2
        return MemoryContext(
            session_id=session_id,
            messages=memory_messages,
            turn_count=total_turns,
            is_expired=False,
        )

    # ── Cleanup ──

    async def cleanup_expired(self) -> int:
        """Delete all expired sessions. Returns count deleted."""
        count = await self.session_repo.delete_expired()
        if count > 0:
            knowledge_sessions_active.dec(count)
            knowledge_session_expired_total.inc(count)
            logger.info(
                "knowledge.memory.cleanup",
                sessions_deleted=count,
            )
        return count

    # ── Turn Enforcement (FIFO) ──

    async def _enforce_max_turns(self, session_id: UUID) -> None:
        """FIFO truncation: if total messages > MAX_TURNS * 2, remove oldest pair."""
        msg_count = await self.message_repo.count_messages(session_id)
        max_msgs = MAX_TURNS * 2

        if msg_count <= max_msgs:
            return

        excess = msg_count - max_msgs
        # Get the N oldest messages (oldest first) by listing page 1 with the excess count
        from sqlalchemy import select as sa_select, delete as sa_delete
        from backend.models.knowledge_message import KnowledgeMessage

        stmt = (
            sa_select(KnowledgeMessage.id)
            .where(KnowledgeMessage.session_id == session_id)
            .order_by(KnowledgeMessage.created_at.asc())
            .limit(excess)
        )
        result = await self._session.execute(stmt)
        ids_to_delete = [row[0] for row in result.all()]

        if ids_to_delete:
            delete_stmt = sa_delete(KnowledgeMessage).where(
                KnowledgeMessage.id.in_(ids_to_delete),
            )
            await self._session.execute(delete_stmt)

        knowledge_memory_truncation_total.inc(excess)

        logger.info(
            "knowledge.memory.truncated",
            session_id=str(session_id),
            excess_messages=excess,
            max_allowed=max_msgs,
        )

    # ── Helpers ──

    @staticmethod
    def _to_summary(sess: KnowledgeSession, msg_count: int) -> MemorySessionSummary:
        return MemorySessionSummary(
            id=sess.id,
            title=sess.title,
            created_at=sess.created_at,
            last_activity_at=sess.last_activity_at,
            expires_at=sess.expires_at,
            is_active=sess.is_active,
            message_count=msg_count,
        )
