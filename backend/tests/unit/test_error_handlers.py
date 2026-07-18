"""Tests for global error handlers."""

import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app


class TestErrorHandlers:
    @pytest.mark.asyncio
    async def test_404_returns_fastapi_default(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/nonexistent-route")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_health_route_works(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_error_response_format(self):
        # FastAPI 404 already returns {"detail": "Not Found"}
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/nonexistent-route")
        assert response.status_code == 404
        # Default FastAPI 404 format
        data = response.json()
        assert "detail" in data
