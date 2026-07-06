"""Tests for request context middleware headers."""

import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app


class TestMiddlewareHeaders:
    @pytest.mark.asyncio
    async def test_request_id_header(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) == 16

    @pytest.mark.asyncio
    async def test_correlation_id_header(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
        assert "X-Correlation-ID" in response.headers
        assert len(response.headers["X-Correlation-ID"]) == 16

    @pytest.mark.asyncio
    async def test_passthrough_request_id(self):
        transport = ASGITransport(app=app)
        headers = {"X-Request-ID": "custom-id-12345"}
        async with AsyncClient(
            transport=transport, base_url="http://test", headers=headers
        ) as client:
            response = await client.get("/health")
        assert response.headers["X-Request-ID"] == "custom-id-12345"

    @pytest.mark.asyncio
    async def test_passthrough_correlation_id(self):
        transport = ASGITransport(app=app)
        headers = {"X-Correlation-ID": "my-correlation"}
        async with AsyncClient(
            transport=transport, base_url="http/test", headers=headers
        ) as client:
            response = await client.get("/health")
        assert response.headers["X-Correlation-ID"] == "my-correlation"
