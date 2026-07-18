"""Tests for health check endpoints and HealthService."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.core.observability import (
    DatabaseHealthCheck,
    HealthService,
)


class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_health_root(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_health_live(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    @pytest.mark.asyncio
    async def test_version(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/version")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "title" in data

    @pytest.mark.asyncio
    async def test_health_ready(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "checks" in data


class TestDatabaseHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_interface(self):
        check = DatabaseHealthCheck()
        assert check.name == "database"
        result = await check.check()
        assert "status" in result


class TestHealthService:
    @pytest.mark.asyncio
    async def test_check_all_returns_checks(self):
        result = await HealthService.check_all()
        assert "status" in result
        assert "checks" in result
        assert "database" in result["checks"]
        assert "version" in result
