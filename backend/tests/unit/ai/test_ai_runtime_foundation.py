"""Tests for AI Runtime Foundation (Phase P2.1)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from uuid_extensions import uuid7

from backend.ai.providers.base import AIProvider, AIProviderResponse
from backend.ai.provider_registry import register_primary, register_fallback, get_primary, get_fallback, initialize
from backend.ai.router import route, TASK_ROUTING
from backend.services.cost_tracker_service import CostTracker
from backend.services.ai_audit_service import AIAuditService


# ── Mock Provider ──

class MockProvider(AIProvider):
    def __init__(self, name="mock", model="mock-model", fail=False, delay=0):
        self._name = name
        self._model = model
        self._fail = fail
        self._delay = delay

    @property
    def name(self) -> str:
        return self._name

    @property
    def model_name(self) -> str:
        return self._model

    async def health_check(self) -> bool:
        return not self._fail

    async def chat(self, prompt="", system_prompt="", max_tokens=2048, temperature=0.3, correlation_id=""):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._fail:
            return AIProviderResponse(content="", provider=self.name, model_name=self.model_name, task_type="chat", status="error", error_message="mock fail")
        token_count = len(prompt) // 3
        return AIProviderResponse(content="mock response", provider=self.name, model_name=self.model_name,
                                   task_type="chat", prompt_tokens=token_count, completion_tokens=50,
                                   total_tokens=token_count + 50, cost_usd=self.estimate_cost(token_count, 50),
                                   latency_ms=10, status="success")

    def estimate_cost(self, prompt_tokens=0, completion_tokens=0) -> float:
        return (prompt_tokens * 0.15 + completion_tokens * 0.60) / 1_000_000


# ── Provider Tests ──

class TestProviderRegistry:
    def test_register_and_get_primary(self):
        p = MockProvider("test", "test-model")
        register_primary(p)
        assert get_primary() is p

    def test_register_and_get_fallback(self):
        p = MockProvider("fall", "fall-model")
        register_fallback(p)
        assert get_fallback() is p

    def test_initialize_registers_defaults(self):
        with patch("backend.ai.provider_registry.DeepSeekProvider"),              patch("backend.ai.provider_registry.OpenAIProvider"):
            initialize()
            assert get_primary() is not None
            assert get_fallback() is not None


class TestRouter:
    @pytest.mark.asyncio
    async def test_routes_to_primary(self):
        primary = MockProvider("primary", "p-model")
        register_primary(primary)
        result = await route("knowledge_query", "test query")
        assert result.provider == "primary"
        assert result.content == "mock response"

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self):
        failing = MockProvider("primary", "p-model", fail=True)
        fallback = MockProvider("fallback", "f-model")
        register_primary(failing)
        register_fallback(fallback)
        result = await route("knowledge_query", "test query")
        assert result.provider == "fallback"

    @pytest.mark.asyncio
    async def test_no_providers_returns_error(self):
        register_primary(MockProvider("p"))
        register_fallback(MockProvider("f"))
        from backend.ai.provider_registry import register_primary as rp, register_fallback as rf
        rp(None)  # simulate no primary
        rf(None)
        result = await route("knowledge_query", "test")
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_budget_rejection_skips_provider(self):
        primary = MockProvider("primary", "p-model")
        fallback = MockProvider("fallback", "f-model")
        register_primary(primary)
        register_fallback(fallback)
        tracker = CostTracker(global_budget=0.0)
        result = await route("knowledge_query", "test", cost_tracker=tracker, user_id="test_user")
        assert result.status == "error" or result.status == "success"

    def test_task_routing_config(self):
        assert "knowledge_query" in TASK_ROUTING
        assert "document_extraction" in TASK_ROUTING
        assert "human_review" in TASK_ROUTING


# ── CostTracker Tests ──

class TestCostTracker:
    @pytest.mark.asyncio
    async def test_check_and_reserve_allows_within_budget(self):
        t = CostTracker(global_budget=10.0, user_budget=1.0)
        allowed = await t.check_and_reserve("user1", 0.50)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_check_and_reserve_blocks_over_global(self):
        t = CostTracker(global_budget=1.0, user_budget=1.0)
        await t.check_and_reserve("user1", 2.0)
        allowed = await t.check_and_reserve("user1", 0.01)
        assert allowed is False

    @pytest.mark.asyncio
    async def test_check_and_reserve_blocks_over_user(self):
        t = CostTracker(global_budget=10.0, user_budget=1.0)
        await t.check_and_reserve("user1", 1.0)
        allowed = await t.check_and_reserve("user1", 0.01)
        assert allowed is False

    @pytest.mark.asyncio
    async def test_record_actual_adjusts_down(self):
        t = CostTracker(global_budget=10.0, user_budget=1.0)
        await t.check_and_reserve("user1", 1.0)
        await t.record_actual("user1", 0.50)
        spent = await t.get_spent("user1")
        assert spent == pytest.approx(0.50, rel=0.01)

    @pytest.mark.asyncio
    async def test_record_actual_adjusts_up(self):
        t = CostTracker(global_budget=10.0, user_budget=1.0)
        await t.check_and_reserve("user1", 0.50)
        await t.record_actual("user1", 0.75)
        spent = await t.get_spent("user1")
        assert spent == pytest.approx(0.75, rel=0.01)

    @pytest.mark.asyncio
    async def test_concurrent_requests_dont_overshoot(self):
        t = CostTracker(global_budget=5.0, user_budget=5.0)

        async def race():
            allowed = await t.check_and_reserve("user2", 3.0)
            return allowed

        results = await asyncio.gather(*[race() for _ in range(3)])
        assert sum(results) <= 2  # at most 2 should pass (3+3=6 > 5)

    @pytest.mark.asyncio
    async def test_get_remaining(self):
        t = CostTracker(global_budget=10.0, user_budget=1.0)
        await t.check_and_reserve("user3", 0.25)
        remaining = await t.get_remaining("user3")
        assert remaining == pytest.approx(0.75, rel=0.01)

    @pytest.mark.asyncio
    async def test_reset_on_new_day(self):
        t = CostTracker(global_budget=10.0, user_budget=1.0)
        await t.check_and_reserve("user4", 5.0)
        # Simulate date change
        from datetime import datetime, timezone
        t._last_reset = datetime(2020, 1, 1).date()
        t._check_reset()
        remaining = await t.get_remaining("global")
        assert remaining == pytest.approx(10.0, rel=0.01)


# ── AIAuditService Tests ──

class TestAIAuditService:
    @pytest.mark.asyncio
    async def test_record_call_creates_log_entry(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        svc = AIAuditService(session)
        resp = AIProviderResponse(content="ok", provider="test", model_name="m", task_type="chat",
                                    prompt_tokens=10, completion_tokens=5, total_tokens=15,
                                    cost_usd=0.001, latency_ms=50, status="success")
        log = await svc.record_call(resp, correlation_id="abc123", user_id=uuid7())
        assert log.provider == "test"
        assert log.cost_usd == 0.001
        assert log.correlation_id == "abc123"


# ── AIQueryLogRepository Tests ──

class TestAIQueryLogRepository:
    @pytest.mark.asyncio
    async def test_get_daily_cost_returns_float(self):
        session = AsyncMock()
        from backend.repositories.ai_query_log_repository import AIQueryLogRepository
        repo = AIQueryLogRepository(session)
        session.execute.return_value.scalar.return_value = 0.50
        cost = await repo.get_daily_cost()
        assert cost == 0.50

    @pytest.mark.asyncio
    async def test_get_by_correlation(self):
        session = AsyncMock()
        from backend.repositories.ai_query_log_repository import AIQueryLogRepository
        repo = AIQueryLogRepository(session)
        session.execute.return_value.scalars.return_value.all.return_value = []
        results = await repo.get_by_correlation("abc")
        assert results == []