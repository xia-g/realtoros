"""Tests for APScheduler integration."""

from unittest.mock import AsyncMock, patch

import pytest
from uuid_extensions import uuid7

from backend.core.scheduler import (
    _TASK_REGISTRY,
    _build_trigger,
    register_task,
    execute_job,
)


@pytest.fixture(autouse=True)
def clear_registry():
    _TASK_REGISTRY.clear()
    yield
    _TASK_REGISTRY.clear()


class TestRegisterTask:
    async def test_registers_handler(self):
        async def handler(job_id, payload):
            pass
        register_task("test_type", handler)
        assert "test_type" in _TASK_REGISTRY
        assert _TASK_REGISTRY["test_type"] is handler


class TestExecuteJob:
    async def test_executes_registered_handler(self):
        mock_handler = AsyncMock()
        register_task("test_type", mock_handler)
        job_id = uuid7()
        await execute_job(job_id, "test_type", {"key": "value"})
        mock_handler.assert_awaited_once_with(job_id=job_id, payload={"key": "value"})

    async def test_logs_error_for_unregistered(self):
        with patch("backend.core.scheduler.logger") as mock_log:
            await execute_job(uuid7(), "unknown_type", {})
            mock_log.error.assert_called_once()

    async def test_handles_handler_exception(self):
        async def failing_handler(job_id, payload):
            raise RuntimeError("test error")
        register_task("failing", failing_handler)
        with patch("backend.core.scheduler.logger") as mock_log:
            await execute_job(uuid7(), "failing", {})
            mock_log.exception.assert_called_once()


class TestBuildTrigger:
    def test_interval_trigger(self):
        trigger = _build_trigger("interval", {"seconds": 30})
        assert trigger is not None

    def test_cron_trigger(self):
        trigger = _build_trigger("cron", {"hour": 3, "minute": 0})
        assert trigger is not None

    def test_date_trigger(self):
        from datetime import datetime
        trigger = _build_trigger("date", {"run_date": datetime(2026, 12, 31)})
        assert trigger is not None

    def test_once_defaults_to_now(self):
        trigger = _build_trigger("once", {})
        assert trigger is not None
