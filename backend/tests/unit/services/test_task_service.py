"""Tests for TaskService."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from uuid_extensions import uuid7

from backend.core.exceptions import NotFoundError, ValidationError
from backend.services.task_service import TaskService


@pytest.fixture
def service():
    session = AsyncMock()
    session.flush = AsyncMock()
    service = TaskService(session)
    service.repo = AsyncMock()
    return service


class TestCreateTask:
    async def test_creates_task(self, service):
        service.repo.create = AsyncMock(return_value=MagicMock(id=uuid7()))
        result = await service.create_task(title="Call client")
        assert result is not None

    async def test_requires_title(self, service):
        with pytest.raises(ValidationError):
            await service.create_task(title="")


class TestCompleteTask:
    async def test_complete(self, service):
        task = MagicMock(status="in_progress")
        service.repo.get = AsyncMock(return_value=task)
        result = await service.complete_task(task.id, uuid7())
        assert result.status == "completed"

    async def test_not_found(self, service):
        service.repo.get = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await service.complete_task(uuid7(), uuid7())


class TestReopenTask:
    async def test_reopen(self, service):
        task = MagicMock(status="completed", completed_by=uuid7(), completed_at=MagicMock())
        service.repo.get = AsyncMock(return_value=task)
        result = await service.reopen_task(task.id)
        assert result.status == "in_progress"
        assert result.completed_by is None
