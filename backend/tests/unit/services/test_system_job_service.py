"""Tests for SystemJobService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from uuid_extensions import uuid7

from backend.services.system_job_service import SystemJobService


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def service(mock_session):
    svc = SystemJobService(mock_session)
    svc.repo = AsyncMock()
    return svc


def make_job(**kwargs):
    defaults = dict(
        id=uuid7(),
        name="test_job",
        task_type="notification_cleanup",
        status="pending",
        priority=0,
        trigger="once",
        trigger_args={},
        payload={},
        result=None,
        error_message=None,
        retry_count=0,
        max_retries=3,
        scheduled_at=None,
        started_at=None,
        completed_at=None,
        created_at=None,
    )
    defaults.update(kwargs)
    return MagicMock(**defaults)


class TestCreateJob:
    async def test_creates_successfully(self, service):
        service.repo.create = AsyncMock(return_value=make_job())
        result = await service.create_job(name="test", task_type="cleanup")
        assert result is not None
        assert result["name"] == "test_job"

    async def test_defaults(self, service):
        service.repo.create = AsyncMock(return_value=make_job(trigger="once"))
        result = await service.create_job(name="test", task_type="cleanup")
        assert result["trigger"] == "once"
        assert result["max_retries"] == 3

    async def test_with_priority(self, service):
        service.repo.create = AsyncMock(return_value=make_job(priority=10))
        result = await service.create_job(name="test", task_type="cleanup", priority=10)
        assert result["priority"] == 10


class TestGetJob:
    async def test_returns_job(self, service):
        service.repo.get = AsyncMock(return_value=make_job())
        result = await service.get_job(uuid7())
        assert result is not None
        assert result["name"] == "test_job"

    async def test_returns_none_on_missing(self, service):
        service.repo.get = AsyncMock(return_value=None)
        result = await service.get_job(uuid7())
        assert result is None


class TestRetryJob:
    async def test_increments_retry(self, service):
        job = make_job(retry_count=1)
        service.repo.increment_retry = AsyncMock(return_value=job)
        result = await service.retry_job(uuid7())
        assert result is not None
        assert result["retry_count"] == 1

    async def test_returns_none_on_missing(self, service):
        service.repo.increment_retry = AsyncMock(return_value=None)
        result = await service.retry_job(uuid7())
        assert result is None


class TestCancelJob:
    async def test_cancels(self, service):
        service.repo.get = AsyncMock(return_value=make_job())
        result = await service.cancel_job(uuid7())
        assert result is not None

    async def test_not_found(self, service):
        service.repo.get = AsyncMock(return_value=None)
        result = await service.cancel_job(uuid7())
        assert result is None
