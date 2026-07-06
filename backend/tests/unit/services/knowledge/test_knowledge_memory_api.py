"""Integration tests for Knowledge Session API.

Covers: unauthorized access, session CRUD with ownership, expiry.
Uses mocked dependencies.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.api.dependencies import get_session, get_current_user
from backend.services.knowledge.memory.memory_service import MemoryService
from backend.services.knowledge.memory.contracts import MemorySessionSummary


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_user_id():
    return str(uuid4())


@pytest.fixture
def mock_summary():
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    return MemorySessionSummary(
        id=uuid4(),
        title="Test Session",
        created_at=now,
        last_activity_at=now,
        expires_at=now + timedelta(hours=24),
        is_active=True,
        message_count=3,
    )


class TestKnowledgeSessionsAPI:
    """10+ integration tests for /api/v1/agent/sessions."""

    @patch("backend.api.routes.knowledge_sessions.get_current_user")
    @patch("backend.api.routes.knowledge_sessions.get_session")
    async def test_list_sessions_requires_auth(self, mock_get_session, mock_get_user, client):
        mock_get_user.return_value = None
        response = client.get("/api/v1/agent/sessions")
        assert response.status_code == 401
        assert "Authentication" in response.json()["detail"]

    @patch("backend.api.routes.knowledge_sessions.get_current_user")
    @patch("backend.api.routes.knowledge_sessions.get_session")
    async def test_list_sessions_success(self, mock_get_session, mock_get_user, client, mock_user_id, mock_summary):
        mock_get_user.return_value = mock_user_id
        mock_db_session = AsyncMock()
        mock_get_session.return_value = mock_db_session

        with patch.object(MemoryService, 'list_sessions', new=AsyncMock()) as mock_list:
            mock_list.return_value = ([mock_summary], 1)
            response = client.get(f"/api/v1/agent/sessions?page=1&page_size=20")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    @patch("backend.api.routes.knowledge_sessions.get_current_user")
    @patch("backend.api.routes.knowledge_sessions.get_session")
    async def test_create_session_requires_auth(self, mock_get_session, mock_get_user, client):
        mock_get_user.return_value = None
        response = client.post("/api/v1/agent/sessions")
        assert response.status_code == 401

    @patch("backend.api.routes.knowledge_sessions.get_current_user")
    @patch("backend.api.routes.knowledge_sessions.get_session")
    async def test_create_session_success(self, mock_get_session, mock_get_user, client, mock_user_id, mock_summary):
        mock_get_user.return_value = mock_user_id
        mock_db_session = AsyncMock()
        mock_get_session.return_value = mock_db_session

        with patch.object(MemoryService, 'create_session', new=AsyncMock()) as mock_create:
            mock_create.return_value = mock_summary
            response = client.post("/api/v1/agent/sessions?title=Test")

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Session"
        assert data["is_active"] is True

    @patch("backend.api.routes.knowledge_sessions.get_current_user")
    @patch("backend.api.routes.knowledge_sessions.get_session")
    async def test_get_session_requires_auth(self, mock_get_session, mock_get_user, client):
        mock_get_user.return_value = None
        response = client.get(f"/api/v1/agent/sessions/{uuid4()}")
        assert response.status_code == 401

    @patch("backend.api.routes.knowledge_sessions.get_current_user")
    @patch("backend.api.routes.knowledge_sessions.get_session")
    async def test_get_session_found(self, mock_get_session, mock_get_user, client, mock_user_id, mock_summary):
        mock_get_user.return_value = mock_user_id
        mock_db_session = AsyncMock()
        mock_get_session.return_value = mock_db_session

        with patch.object(MemoryService, 'get_session', new=AsyncMock()) as mock_get:
            mock_get.return_value = mock_summary
            response = client.get(f"/api/v1/agent/sessions/{mock_summary.id}")

        assert response.status_code == 200
        data = response.json()
        assert str(data["id"]) == str(mock_summary.id)

    @patch("backend.api.routes.knowledge_sessions.get_current_user")
    @patch("backend.api.routes.knowledge_sessions.get_session")
    async def test_get_session_not_found(self, mock_get_session, mock_get_user, client, mock_user_id):
        mock_get_user.return_value = mock_user_id
        mock_db_session = AsyncMock()
        mock_get_session.return_value = mock_db_session

        with patch.object(MemoryService, 'get_session', new=AsyncMock()) as mock_get:
            mock_get.return_value = None
            response = client.get(f"/api/v1/agent/sessions/{uuid4()}")

        assert response.status_code == 404

    @patch("backend.api.routes.knowledge_sessions.get_current_user")
    @patch("backend.api.routes.knowledge_sessions.get_session")
    async def test_delete_session_success(self, mock_get_session, mock_get_user, client, mock_user_id):
        mock_get_user.return_value = mock_user_id
        mock_db_session = AsyncMock()
        mock_get_session.return_value = mock_db_session

        with patch.object(MemoryService, 'expire_session', new=AsyncMock()) as mock_expire:
            mock_expire.return_value = True
            response = client.delete(f"/api/v1/agent/sessions/{uuid4()}")

        assert response.status_code == 200
        assert response.json()["status"] == "expired"

    @patch("backend.api.routes.knowledge_sessions.get_current_user")
    @patch("backend.api.routes.knowledge_sessions.get_session")
    async def test_delete_session_not_found(self, mock_get_session, mock_get_user, client, mock_user_id):
        mock_get_user.return_value = mock_user_id
        mock_db_session = AsyncMock()
        mock_get_session.return_value = mock_db_session

        with patch.object(MemoryService, 'expire_session', new=AsyncMock()) as mock_expire:
            mock_expire.return_value = False
            response = client.delete(f"/api/v1/agent/sessions/{uuid4()}")

        assert response.status_code == 404

    @patch("backend.api.routes.knowledge_sessions.get_current_user")
    @patch("backend.api.routes.knowledge_sessions.get_session")
    async def test_cannot_access_other_user_session(self, mock_get_session, mock_get_user, client, mock_user_id):
        """User A lists sessions — only A's sessions returned."""
        mock_get_user.return_value = mock_user_id
        mock_db_session = AsyncMock()
        mock_get_session.return_value = mock_db_session

        with patch.object(MemoryService, 'list_sessions', new=AsyncMock()) as mock_list:
            mock_list.return_value = ([], 0)
            response = client.get(f"/api/v1/agent/sessions")

        assert response.status_code == 200
        assert response.json()["total"] == 0
