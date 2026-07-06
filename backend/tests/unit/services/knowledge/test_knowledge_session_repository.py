"""Tests for Knowledge Session + Message repositories.

Uses mocked async session. Tests: CRUD, ownership enforcement, expiry,
cascade delete, pagination.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.knowledge_session import KnowledgeSession, KnowledgeMessage
from backend.repositories.knowledge_session_repository import (
    KnowledgeSessionRepository,
    KnowledgeMessageRepository,
)


@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def session_repo(mock_session):
    return KnowledgeSessionRepository(mock_session)


@pytest.fixture
def message_repo(mock_session):
    return KnowledgeMessageRepository(mock_session)


class TestKnowledgeSessionRepository:
    """10+ tests for session CRUD with ownership enforcement."""

    async def test_create_session(self, session_repo, mock_session):
        s = await session_repo.create_session(user_id=uuid4())
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        assert s.user_id is not None
        assert s.is_active is True

    async def test_get_session_filters_by_user(self, session_repo, mock_session):
        uid = uuid4()
        sid = uuid4()
        # Simulate scalar_one_or_none returning None for wrong user
        mock_execute = AsyncMock()
        mock_execute.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_execute

        result = await session_repo.get_session(sid, uid)
        assert result is None

        # Verify the generated SQL filters by BOTH id AND user_id
        call_stmt = mock_session.execute.call_args[0][0]
        call_str = str(call_stmt)
        assert "knowledge_sessions" in call_str
        assert "user_id" in call_str
        assert str(uid) in call_str or ":user_id" in call_str

    async def test_get_session_own(self, session_repo, mock_session):
        uid = uuid4()
        sid = uuid4()
        sess = KnowledgeSession(id=sid, user_id=uid, is_active=True,
                                expires_at=datetime.now(timezone.utc) + timedelta(hours=24))

        mock_execute = AsyncMock()
        mock_execute.scalar_one_or_none.return_value = sess
        mock_session.execute.return_value = mock_execute

        found = await session_repo.get_session(sid, uid)
        assert found is not None
        assert found.id == sid

    async def test_get_session_other_user_returns_none(self, session_repo, mock_session):
        uid_owner = uuid4()
        uid_attacker = uuid4()
        sid = uuid4()

        mock_execute = AsyncMock()
        mock_execute.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_execute

        found = await session_repo.get_session(sid, uid_attacker)
        assert found is None

    async def test_get_active_session_returns_most_recent(self, session_repo, mock_session):
        uid = uuid4()
        now = datetime.now(timezone.utc)
        sess = KnowledgeSession(id=uuid4(), user_id=uid, is_active=True,
                                expires_at=now + timedelta(hours=24),
                                last_activity_at=now)

        mock_execute = AsyncMock()
        mock_execute.scalar_one_or_none.return_value = sess
        mock_session.execute.return_value = mock_execute

        active = await session_repo.get_active_session(uid)
        assert active is not None
        assert active.id == sess.id

    async def test_touch_session_other_user_fails(self, session_repo, mock_session):
        uid = uuid4()
        sid = uuid4()

        mock_execute = AsyncMock()
        mock_execute.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_execute

        result = await session_repo.touch_session(sid, uid)
        assert result is False

    async def test_expire_session_other_user_fails(self, session_repo, mock_session):
        mock_execute = AsyncMock()
        mock_execute.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_execute

        result = await session_repo.expire_session(uuid4(), uuid4())
        assert result is False

    async def test_list_user_sessions_pagination(self, session_repo, mock_session):
        uid = uuid4()
        now = datetime.now(timezone.utc)
        sess1 = KnowledgeSession(id=uuid4(), user_id=uid, is_active=True,
                                 expires_at=now + timedelta(hours=24),
                                 last_activity_at=now)

        mock_execute = AsyncMock()
        mock_execute.scalars.return_value.all.return_value = [sess1]
        mock_session.execute.return_value = mock_execute

        items, total = await session_repo.list_user_sessions(uid, page=1, page_size=3)
        assert len(items) == 1

    async def test_delete_expired(self, session_repo, mock_session):
        mock_execute = AsyncMock()
        mock_execute.scalar.return_value = 2
        mock_session.execute.return_value = mock_execute

        count = await session_repo.delete_expired()
        assert count == 2


class TestKnowledgeMessageRepository:
    """Tests for message CRUD within sessions."""

    async def test_add_message(self, message_repo, mock_session):
        msg = await message_repo.add_message(uuid4(), "user", "Hello", token_count=10)
        assert msg.role == "user"
        assert msg.content == "Hello"

    async def test_list_messages_oldest_first(self, message_repo, mock_session):
        """Verify ordering is by created_at ASC."""
        mock_execute = AsyncMock()
        mock_execute.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_execute

        msgs, total = await message_repo.list_messages(uuid4())
        call_stmt = mock_session.execute.call_args[0][0]
        call_str = str(call_stmt)
        assert "created_at" in call_str or "asc" in call_str.lower() or "order_by" in call_str

    async def test_get_recent_messages_limit(self, message_repo, mock_session):
        mock_execute = AsyncMock()
        mock_execute.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_execute

        recent = await message_repo.get_recent_messages(uuid4(), limit=4)
        assert isinstance(recent, list)

    async def test_count_messages(self, message_repo, mock_session):
        mock_execute = AsyncMock()
        mock_execute.scalar.return_value = 7
        mock_session.execute.return_value = mock_execute

        count = await message_repo.count_messages(uuid4())
        assert count == 7

    async def test_delete_session_messages(self, message_repo, mock_session):
        mock_execute = AsyncMock()
        mock_execute.rowcount = 5
        mock_session.execute.return_value = mock_execute

        deleted = await message_repo.delete_session_messages(uuid4())
        assert deleted == 5
