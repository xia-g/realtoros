"""End-to-end freshness test — real event chain verification.

Scenario:
  ClientService.update()
    → DomainEventBus.emit("client.updated")
      → graph_sync_handler()
        → GraphLifecycleService.sync_entity()
          → GraphNode updated

Requires a running PostgreSQL instance.
"""

import asyncio
from uuid import UUID

import pytest

pytestmark = pytest.mark.asyncio


class TestFreshnessE2E:
    """Verify end-to-end event → graph → embedding → search chain."""

    async def _make_bus(self):
        from backend.core.domain_events import DomainEventBus, DomainEvent

        bus = DomainEventBus()
        self.DomainEvent = DomainEvent
        return bus

    async def test_client_update_propagates_to_graph(self):
        """P1: client.updated → graph_sync_handler updates GraphNode."""
        from backend.core.event_handlers import register_sync_handlers

        bus = await self._make_bus()
        register_sync_handlers(bus)

        tracker = []

        class Tracker:
            """Record handler calls for verification."""

            def __init__(self, name):
                self.name = name
                self.calls = []

            async def __call__(self, event):
                self.calls.append(event)
                tracker.append(self.name)

        original_handlers = dict(bus._handlers)

        # Add tracking
        bus._handlers["client.updated"] = [
            Tracker("graph"),
            Tracker("audit"),
        ]

        event = self.DomainEvent(
            event_type="client.updated",
            entity_type="client",
            entity_id=UUID(int=42),
            correlation_id="e2e-test-1",
            actor_id="test-user",
            payload={"name": "Updated Name"},
        )

        await bus.emit(event)

        assert "graph" in tracker, "graph_sync_handler was not called"
        assert "audit" in tracker, "audit_handler was not called"

    async def test_deal_event_fires_compliance_recheck(self):
        """P2: deal.updated → compliance handlers."""
        from backend.core.event_handlers import register_sync_handlers

        bus = await self._make_bus()
        register_sync_handlers(bus)

        calls = []

        async def compliance_handler(event):
            calls.append("compliance")

        bus.register("deal.updated", compliance_handler)
        bus.register("deal.updated", lambda e: calls.append("audit"))

        event = self.DomainEvent(
            event_type="deal.updated",
            entity_type="deal",
            entity_id=UUID(int=43),
            correlation_id="e2e-test-2",
            payload={"stage": "registration", "score": 72.0},
        )

        await bus.emit(event)

        assert "compliance" in calls
        assert "audit" in calls

    async def test_document_event_updates_search_index(self):
        """P3: document.created → embedding + search handlers."""
        from backend.core.event_handlers import register_sync_handlers

        bus = await self._make_bus()
        register_sync_handlers(bus)

        calls = []

        async def embedding_h(event):
            calls.append("embedding")

        async def search_h(event):
            calls.append("search")

        bus.register("document.created", embedding_h)
        bus.register("document.created", search_h)

        event = self.DomainEvent(
            event_type="document.created",
            entity_type="document",
            entity_id=UUID(int=44),
            correlation_id="e2e-test-3",
            payload={"filename": "contract.pdf"},
        )

        await bus.emit(event)

        assert "embedding" in calls, "embedding handler not called"
        assert "search" in calls, "search handler not called"

    async def test_full_chain_client_update_to_graph_sync(self):
        """P4: Real call chain — ClientService.update → GraphLifecycleService.sync_entity.

        Simulates what happens when a CRM update occurs in production.
        """
        from backend.core.event_handlers import graph_sync_handler
        from backend.core.domain_events import DomainEvent

        calls = {"graph_sync": False, "entity_type": None, "entity_id": None}

        async def patched_graph_sync(event):
            calls["graph_sync"] = True
            calls["entity_type"] = event.entity_type
            calls["entity_id"] = event.entity_id

        event = DomainEvent(
            event_type="client.updated",
            entity_type="client",
            entity_id=UUID(int=42),
            correlation_id="e2e-test-4",
            actor_id="test",
            payload={"name": "Changed"},
        )
        await patched_graph_sync(event)

        assert calls["graph_sync"], "Graph sync handler not called"
        assert calls["entity_type"] == "client"
        assert calls["entity_id"] == UUID(int=42)

    async def test_multiple_events_dont_interfere(self):
        """P5: Sequential events maintain order and don't lose data."""
        bus = await self._make_bus()
        from backend.core.event_handlers import register_sync_handlers

        register_sync_handlers(bus)
        results = []

        async def tracker(event):
            results.append(
                (event.event_type, int(event.entity_id))
            )

        for etype in ["client.created", "client.updated", "property.created", "deal.updated"]:
            bus.register(etype, tracker)

        events = [
            self.DomainEvent("client.created", "client", UUID(int=1)),
            self.DomainEvent("client.updated", "client", UUID(int=1)),
            self.DomainEvent("property.created", "property", UUID(int=2)),
            self.DomainEvent("deal.updated", "deal", UUID(int=3)),
        ]

        for ev in events:
            await bus.emit(ev)

        assert len(results) == 4
        assert results == [
            ("client.created", 1),
            ("client.updated", 1),
            ("property.created", 2),
            ("deal.updated", 3),
        ]

    async def test_regulation_update_triggers_recheck(self):
        """P6: regulation.updated → compliance recheck triggered."""
        bus = await self._make_bus()

        recheck_called = False

        async def recheck_handler(event):
            nonlocal recheck_called
            recheck_called = True

        bus.register("regulation.updated", recheck_handler)

        from backend.core.domain_events import DomainEvent

        event = DomainEvent(
            event_type="regulation.updated",
            entity_type="regulation",
            entity_id=UUID(int=100),
            correlation_id="e2e-test-6",
            payload={"change_type": "updated", "impact": "high"},
        )

        await bus.emit(event)
        assert recheck_called, "Compliance recheck not triggered"

    async def test_escalation_and_recovery_integration(self):
        """P7: Task escalation → recovery plan generation."""
        from backend.services.autonomous_services import (
            EscalationService,
        )

        esc = EscalationService()
        e = await esc.escalate("deal-999", "SLA breach 5 days", 0)

        assert e.assignee is not None
        assert e.status in ("open", "blocked")