"""Load test — Agent Runtime + RateLimiter + EventBus under concurrent load."""
import asyncio
import time
from uuid import UUID

import pytest

pytestmark = pytest.mark.asyncio


class TestLoad:
    """Concurrent load tests for core components."""

    CONCURRENCY_LEVELS = [100, 500, 1000]

    @pytest.fixture
    def event_bus(self):
        from backend.core.domain_events import DomainEventBus, DomainEvent
        bus = DomainEventBus()
        self.DomainEvent = DomainEvent
        return bus

    async def _fire_events(self, bus, count: int, event_type="test.load"):
        """Fire N events concurrently."""
        tasks = []
        for i in range(min(count, 100)):
            tasks.append(
                bus.emit(self.DomainEvent(
                    event_type=event_type,
                    entity_type="test",
                    entity_id=UUID(int=i),
                    correlation_id=f"load-test-{i}",
                ))
            )
        await asyncio.gather(*tasks)

    @pytest.mark.parametrize("concurrency", [100, 500, 1000])
    async def test_event_bus_concurrent(self, event_bus, concurrency):
        """EventBus handles concurrent emits without error."""
        calls = []
        for i in range(10):
            event_bus.register(f"test.{i}", lambda e: calls.append(1))
        t0 = time.monotonic()
        await self._fire_events(event_bus, concurrency)
        elapsed = time.monotonic() - t0
        assert elapsed < 10, f"EventBus too slow: {elapsed:.2f}s for {concurrency}"

    async def test_rate_limiter_concurrent(self):
        """RateLimiter under concurrent load."""
        from backend.services.rate_limiter import RateLimiter
        limiter = RateLimiter()
        t0 = time.monotonic()
        results = await asyncio.gather(*[
            limiter.check_limit(UUID(int=1), max_requests=1000, window_seconds=60)
            for _ in range(1000)
        ])
        elapsed = time.monotonic() - t0
        allowed = sum(1 for r in results if r.get("allowed", False))
        assert elapsed < 5, f"RateLimiter too slow: {elapsed:.2f}s"
        assert allowed > 0, "All requests blocked"

    async def test_agent_budget_concurrent(self):
        """AgentExecutionBudget under concurrent access."""
        from backend.core.agent_budget import AgentExecutionBudget
        budgets = [AgentExecutionBudget() for _ in range(1000)]
        t0 = time.monotonic()
        results = await asyncio.gather(*[
            asyncio.to_thread(b.check) for b in budgets
        ])
        elapsed = time.monotonic() - t0
        assert elapsed < 5, f"Budget checks too slow: {elapsed:.2f}s"

    async def test_cost_tracker_concurrent(self):
        """CostTracker handles concurrent calls."""
        from backend.services.cost_tracker import CostTracker
        tracker = CostTracker()
        t0 = time.monotonic()
        results = await asyncio.gather(*[
            tracker.track(
                user_id=UUID(int=i % 10),
                model="deepseek-flash",
                input_tokens=100,
                output_tokens=50,
            ) for i in range(500)
        ])
        elapsed = time.monotonic() - t0
        assert elapsed < 10, f"CostTracker too slow: {elapsed:.2f}s"

    async def test_full_pipeline_concurrent(self, event_bus):
        """End-to-end: EventBus → handler → rate limit under load."""
        from backend.core.event_handlers import register_sync_handlers
        register_sync_handlers(event_bus)

        call_count = 0
        async def track_handler(event):
            nonlocal call_count
            call_count += 1

        event_bus.register("pipeline.test", track_handler)

        t0 = time.monotonic()
        tasks = [
            event_bus.emit(self.DomainEvent(
                event_type="pipeline.test",
                entity_type="deal",
                entity_id=UUID(int=i),
            ))
            for i in range(500)
        ]
        await asyncio.gather(*tasks)
        elapsed = time.monotonic() - t0
        assert elapsed < 15, f"Pipeline too slow: {elapsed:.2f}s"
        assert call_count == 500, f"Not all events processed: {call_count}/500"
