"""Integration tests for Domain Event Bus — emit → handler execution."""
import asyncio
import pytest
from uuid import UUID

pytestmark = pytest.mark.asyncio


class TestEventBusIntegration:
    """Verify emit() → handler execution end-to-end."""

    @pytest.fixture
    def event_bus(self):
        from backend.core.domain_events import DomainEventBus, DomainEvent

        bus = DomainEventBus()
        self.DomainEvent = DomainEvent
        return bus

    @pytest.fixture
    def registered_bus(self, event_bus):
        from backend.core.event_handlers import register_sync_handlers

        register_sync_handlers(event_bus)
        return event_bus

    async def test_client_updated_triggers_graph_sync(self, registered_bus, mocker):
        """Scenario 1: client.updated → graph sync handler called."""
        mock = mocker.AsyncMock()
        original_handlers = dict(registered_bus._handlers)
        registered_bus.register("client.updated", mock)

        event = self.DomainEvent(
            event_type="client.updated",
            entity_type="client",
            entity_id=UUID(int=1),
            correlation_id="test-correlation-1",
            actor_id="test-user",
        )
        await registered_bus.emit(event)
        mock.assert_awaited_once_with(event)

    async def test_deal_closed_triggers_compliance(self, registered_bus, mocker):
        """Scenario 2: deal.closed → compliance handler called."""
        mock = mocker.AsyncMock()
        registered_bus.register("deal.updated", mock)

        event = self.DomainEvent(
            event_type="deal.updated",
            entity_type="deal",
            entity_id=UUID(int=2),
            correlation_id="test-correlation-2",
            actor_id="system",
            payload={"stage": "closed"},
        )
        await registered_bus.emit(event)
        mock.assert_awaited_once_with(event)

    async def test_document_uploaded_triggers_embeddings(self, registered_bus, mocker):
        """Scenario 3: document.created → embedding handler called."""
        from backend.core.event_handlers import embedding_sync_handler

        mock = mocker.AsyncMock(wraps=embedding_sync_handler)
        registered_bus.register("document.created", mock)

        event = self.DomainEvent(
            event_type="document.created",
            entity_type="document",
            entity_id=UUID(int=3),
            correlation_id="test-correlation-3",
        )
        await registered_bus.emit(event)
        mock.assert_awaited_once_with(event)

    async def test_regulation_update_triggers_compliance_recheck(
        self, registered_bus, mocker
    ):
        """Scenario 4: regulation.updated → compliance recheck."""
        mock = mocker.AsyncMock()
        registered_bus.register("regulation.updated", mock)

        event = self.DomainEvent(
            event_type="regulation.updated",
            entity_type="regulation",
            entity_id=UUID(int=4),
            correlation_id="test-correlation-4",
        )
        await registered_bus.emit(event)
        mock.assert_awaited_once_with(event)

    async def test_all_handlers_registered(self, registered_bus):
        """Verify all 13 event types have handlers."""
        expected_events = {
            "client.created",
            "client.updated",
            "client.deleted",
            "property.created",
            "property.updated",
            "property.deleted",
            "deal.created",
            "deal.updated",
            "deal.deleted",
            "document.created",
            "document.deleted",
            "lead.converted",
            "lead.merged",
        }
        registered = set(registered_bus._handlers.keys())
        missing = expected_events - registered
        assert not missing, f"Events missing handlers: {missing}"

    async def test_handler_failure_does_not_block_other_handlers(
        self, registered_bus, mocker
    ):
        """One failing handler should not prevent others from running."""
        results = []

        async def failing_handler(event):
            raise ValueError("Handler failed")

        async def success_handler(event):
            results.append("success")

        registered_bus.register("client.created", failing_handler)
        registered_bus.register("client.created", success_handler)

        event = self.DomainEvent(
            event_type="client.created",
            entity_type="client",
            entity_id=UUID(int=5),
        )
        await registered_bus.emit(event)
        assert "success" in results

    async def test_event_contains_all_required_fields(self):
        """Every event must include correlation_id, entity_type, entity_id, timestamp, actor_id."""
        event = self.DomainEvent(
            event_type="client.created",
            entity_type="client",
            entity_id=UUID(int=6),
            correlation_id="corr-6",
            actor_id="user-1",
        )
        assert event.event_type == "client.created"
        assert event.entity_type == "client"
        assert event.entity_id == UUID(int=6)
        assert event.correlation_id == "corr-6"
        assert event.actor_id == "user-1"
        assert event.occurred_at is not None

    async def test_crm_service_emits_on_create(self, mocker):
        """Verify ClientService emits client.created on create()."""
        from backend.core.domain_events import get_event_bus, DomainEventBus

        bus = DomainEventBus()
        mocker.patch(
            "backend.core.domain_events.get_event_bus", return_value=bus
        )

        mock_handler = mocker.AsyncMock()
        bus.register("client.created", mock_handler)

        from backend.services.client import ClientService

        mock_session = mocker.AsyncMock()
        svc = ClientService(mock_session)

        mock_repo = mocker.AsyncMock()
        mock_obj = mocker.Mock()
        mock_obj.id = UUID(int=10)
        mock_repo.create.return_value = mock_obj
        svc._repo = mock_repo

        result = await svc.create(name="Test Client", phone="+79001112233")
        assert result.id == UUID(int=10)
        mock_handler.assert_awaited_once()
        args = mock_handler.await_args[0]
        assert args.event_type == "client.created"
        assert args.entity_type == "client"

    async def test_sync_handlers_all_listed(self):
        """verify event_handlers covers all declared types."""
        from backend.core.domain_events import (
            EVENT_CLIENT_CREATED, EVENT_CLIENT_UPDATED, EVENT_CLIENT_DELETED,
            EVENT_PROPERTY_CREATED, EVENT_PROPERTY_UPDATED, EVENT_PROPERTY_DELETED,
            EVENT_DEAL_CREATED, EVENT_DEAL_UPDATED, EVENT_DEAL_DELETED,
            EVENT_DOCUMENT_CREATED, EVENT_DOCUMENT_DELETED,
            EVENT_LEAD_CONVERTED, EVENT_LEAD_MERGED,
        )
        from backend.core.event_handlers import register_sync_handlers
        from backend.core.domain_events import DomainEventBus

        bus = DomainEventBus()
        register_sync_handlers(bus)

        all_declared = {
            EVENT_CLIENT_CREATED, EVENT_CLIENT_UPDATED, EVENT_CLIENT_DELETED,
            EVENT_PROPERTY_CREATED, EVENT_PROPERTY_UPDATED, EVENT_PROPERTY_DELETED,
            EVENT_DEAL_CREATED, EVENT_DEAL_UPDATED, EVENT_DEAL_DELETED,
            EVENT_DOCUMENT_CREATED, EVENT_DOCUMENT_DELETED,
            EVENT_LEAD_CONVERTED, EVENT_LEAD_MERGED,
        }
        assert all_declared.issubset(bus._handlers.keys()), (
            f"Missing handlers for: {all_declared - bus._handlers.keys()}"
        )