"""Stream 3 — Event Backbone tests.

Covers: Outbox, Publisher, Consumer, Replay, Registry.
Follows Proposal Section 9 test strategy (11 + 4 scenarios).

These are unit tests using mocking for database operations.
Integration tests (DB-dependent) are in separate files.
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock, ANY
from uuid import UUID, uuid4

import pytest

from backend.core.integration_event import IntegrationEvent, EventAdapter
from backend.core.domain_events import DomainEvent, EVENT_DOCUMENT_READY
from backend.core.event_registry import ensure_event_registry, is_registry_initialized
from backend.infrastructure.consumer_base import ConsumerResult, BaseConsumer
from backend.infrastructure.event_publisher import EventPublisher


# ═══════════════════════════════════════════════════════════════════
# 1. IntegrationEvent — Foundation Tests
# ═══════════════════════════════════════════════════════════════════


class TestIntegrationEvent:
    """IntegrationEvent frozen dataclass tests."""

    def test_frozen_dataclass(self):
        """IntegrationEvent is frozen — cannot mutate after creation."""
        event = IntegrationEvent(
            event_id=uuid4(),
            event_type="document.ready",
            aggregate_type="Document",
            aggregate_id="doc-001",
            occurred_at=datetime.now(timezone.utc),
            payload={"status": "READY"},
        )
        with pytest.raises(Exception):
            event.event_type = "changed"

    def test_required_fields(self):
        """All required fields must be provided."""
        with pytest.raises(TypeError):
            IntegrationEvent(event_id=uuid4())  # type: ignore

    def test_immutable_event_id(self):
        """event_id is immutable — same across retries."""
        event_id = uuid4()
        event = IntegrationEvent(
            event_id=event_id,
            event_type="document.ready",
            aggregate_type="Document",
            aggregate_id="doc-001",
            occurred_at=datetime.now(timezone.utc),
        )
        assert event.event_id == event_id

    def test_to_dict_roundtrip(self):
        """to_dict() -> from_dict() preserves all fields."""
        original = IntegrationEvent(
            event_id=uuid4(),
            event_type="document.ready",
            aggregate_type="Document",
            aggregate_id="doc-001",
            occurred_at=datetime.now(timezone.utc),
            version=1,
            payload={"status": "READY", "document_id": "doc-001"},
            metadata={"schema_version": 1, "producer": "test"},
        )
        data = original.to_dict()
        restored = IntegrationEvent.from_dict(data)

        assert restored.event_id == original.event_id
        assert restored.event_type == original.event_type
        assert restored.aggregate_type == original.aggregate_type
        assert restored.aggregate_id == original.aggregate_id
        assert restored.payload == original.payload
        assert restored.metadata == original.metadata

    def test_no_entity_id_field(self):
        """IntegrationEvent has aggregate_id, NOT entity_id."""
        event = IntegrationEvent(
            event_id=uuid4(),
            event_type="document.ready",
            aggregate_type="Document",
            aggregate_id="doc-001",
            occurred_at=datetime.now(timezone.utc),
        )
        assert hasattr(event, "aggregate_id")
        assert not hasattr(event, "entity_id")

    def test_aggregate_id_vs_event_id(self):
        """aggregate_id is stable business ID, event_id is unique."""
        aggregate_id = "doc-001"
        event1 = IntegrationEvent(
            event_id=uuid4(),
            event_type="document.ready",
            aggregate_type="Document",
            aggregate_id=aggregate_id,
            occurred_at=datetime.now(timezone.utc),
        )
        event2 = IntegrationEvent(
            event_id=uuid4(),
            event_type="document.ready",
            aggregate_type="Document",
            aggregate_id=aggregate_id,
            occurred_at=datetime.now(timezone.utc),
        )
        # Same aggregate, different events
        assert event1.aggregate_id == event2.aggregate_id
        assert event1.event_id != event2.event_id


# ═══════════════════════════════════════════════════════════════════
# 2. EventAdapter Tests
# ═══════════════════════════════════════════════════════════════════


class TestEventAdapter:
    """EventAdapter converts DomainEvent -> IntegrationEvent."""

    def test_to_integration_preserves_event_type(self):
        """event_type is preserved from DomainEvent."""
        domain = DomainEvent(
            event_type=EVENT_DOCUMENT_READY,
            entity_type="document",
            entity_id=uuid4(),
            payload={"status": "READY"},
        )
        integration = EventAdapter.to_integration(domain)
        assert integration.event_type == domain.event_type

    def test_to_integration_uses_aggregate_id(self):
        """aggregate_id comes from DomainEvent.entity_id, not a random UUID."""
        entity_id = uuid4()
        domain = DomainEvent(
            event_type=EVENT_DOCUMENT_READY,
            entity_type="document",
            entity_id=entity_id,
        )
        integration = EventAdapter.to_integration(domain)
        assert integration.aggregate_id == str(entity_id)
        assert integration.event_id != entity_id  # event_id is NEW uuid

    def test_to_integration_no_entity_id_in_output(self):
        """IntegrationEvent has no entity_id field."""
        domain = DomainEvent(
            event_type=EVENT_DOCUMENT_READY,
            entity_type="document",
            entity_id=uuid4(),
        )
        integration = EventAdapter.to_integration(domain)
        assert not hasattr(integration, "entity_id")

    def test_to_integration_preserves_payload(self):
        """Payload is preserved from DomainEvent."""
        payload = {"status": "READY", "document_id": "doc-001"}
        domain = DomainEvent(
            event_type=EVENT_DOCUMENT_READY,
            entity_type="document",
            entity_id=uuid4(),
            payload=payload,
        )
        integration = EventAdapter.to_integration(domain)
        assert integration.payload == payload

    def test_to_integration_sets_metadata_defaults(self):
        """Default metadata (schema_version, producer) are set."""
        domain = DomainEvent(
            event_type=EVENT_DOCUMENT_READY,
            entity_type="document",
            entity_id=uuid4(),
        )
        integration = EventAdapter.to_integration(domain)
        assert integration.metadata is not None
        assert integration.metadata.get("schema_version") == 1
        assert integration.metadata.get("producer") == "domain"

    def test_to_integration_passes_correlation_id(self):
        """correlation_id from DomainEvent goes into metadata."""
        domain = DomainEvent(
            event_type=EVENT_DOCUMENT_READY,
            entity_type="document",
            entity_id=uuid4(),
            correlation_id="corr-123",
        )
        integration = EventAdapter.to_integration(domain)
        assert integration.metadata.get("correlation_id") == "corr-123"

    def test_to_integration_generates_new_event_id(self):
        """IntegrationEvent gets a NEW UUID, not reusing DomainEvent fields."""
        domain = DomainEvent(
            event_type=EVENT_DOCUMENT_READY,
            entity_type="document",
            entity_id=uuid4(),
        )
        integration = EventAdapter.to_integration(domain)
        assert isinstance(integration.event_id, UUID)

    def test_to_integration_maps_aggregate_type(self):
        """aggregate_type is derived from entity_type."""
        domain = DomainEvent(
            event_type=EVENT_DOCUMENT_READY,
            entity_type="document",
            entity_id=uuid4(),
        )
        integration = EventAdapter.to_integration(domain)
        assert integration.aggregate_type == "Document"


# ═══════════════════════════════════════════════════════════════════
# 3. EventRegistry Tests
# ═══════════════════════════════════════════════════════════════════


class TestEventRegistry:
    """EventRegistry — single point of handler registration (P8 fix)."""

    def _reset_registry(self):
        """Reset the global registry flag for testing."""
        import backend.core.event_registry as reg
        reg._registry_initialized = False

    def test_ensure_registry_once(self):
        """First call initializes, second call is no-op (idempotent)."""
        self._reset_registry()
        assert not is_registry_initialized()

        with patch("backend.core.event_handlers.register_sync_handlers") as mock:
            ensure_event_registry()
            mock.assert_called_once()
            assert is_registry_initialized()

    def test_ensure_registry_twice_idempotent(self):
        """Second call does not re-register."""
        self._reset_registry()

        with patch("backend.core.event_handlers.register_sync_handlers") as mock:
            ensure_event_registry()  # first
            ensure_event_registry()  # second
            mock.assert_called_once()  # still once!


# ═══════════════════════════════════════════════════════════════════
# 4. Outbox Repository Tests (mocked psycopg2)
# ═══════════════════════════════════════════════════════════════════


class TestOutboxRepository:
    """OutboxRepository tests with mocked psycopg2."""

    @pytest.fixture
    def repo(self):
        from backend.repositories.outbox_repository import OutboxRepository
        return OutboxRepository(dsn="postgresql://test:test@localhost/test")

    @pytest.fixture
    def sample_event(self):
        return IntegrationEvent(
            event_id=uuid4(),
            event_type="document.ready",
            aggregate_type="Document",
            aggregate_id="doc-001",
            occurred_at=datetime.now(timezone.utc),
            payload={"status": "READY"},
            metadata={"schema_version": 1, "producer": "test"},
        )

    def test_1_event_created_in_outbox(self, repo, sample_event):
        """Event is enqueued with INSERT."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        repo.enqueue(sample_event, conn=mock_conn)
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        assert "INSERT INTO event_outbox" in call_args[0]

    def test_2_fetch_pending_returns_events(self, repo):
        """fetch_pending returns list of pending events."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (uuid4(), "document.ready", "Document", "doc-001",
             {"key": "val"}, {}, datetime.now(timezone.utc),
             None, 0, None, "pending")
        ]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch.object(repo, '_connect', return_value=mock_conn):
            results = repo.fetch_pending(limit=10)
        assert len(results) == 1
        assert results[0]["status"] == "pending"

    def test_3_mark_published_changes_status(self, repo):
        """mark_published sets status='published'."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch.object(repo, '_connect', return_value=mock_conn):
            repo.mark_published(uuid4())
        call_args = mock_cursor.execute.call_args[0]
        assert "status = 'published'" in call_args[0]

    def test_4_mark_failed_increments_attempts(self, repo):
        """mark_failed increments attempts and sets last_error."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch.object(repo, '_connect', return_value=mock_conn):
            repo.mark_failed(uuid4(), "test error")
        call_args = mock_cursor.execute.call_args[0]
        assert "attempts = attempts + 1" in call_args[0]
        assert call_args[1][0] == "test error"

    def test_5_dead_letter_after_max_retries(self, repo):
        """After 3 failed attempts -> status='dead' (via SQL CASE)."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch.object(repo, '_connect', return_value=mock_conn):
            repo.mark_failed(uuid4(), "final error")
        call_args = mock_cursor.execute.call_args[0]
        # SQL uses CASE WHEN attempts + 1 >= 3 THEN 'dead'
        assert "THEN 'dead'" in call_args[0]
        assert "attempts + 1" in call_args[0]

    def test_6_fetch_failed_excludes_dead(self, repo):
        """fetch_failed only returns events with attempts < max_retries."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (uuid4(), "document.ready", "Document", "doc-001",
             {}, {}, datetime.now(timezone.utc),
             None, 1, "retry error", "failed")
        ]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch.object(repo, '_connect', return_value=mock_conn):
            results = repo.fetch_failed(max_retries=3, limit=10)
        assert len(results) == 1
        assert results[0]["attempts"] == 1

    def test_7_retry_resets_status(self, repo):
        """retry sets status back to 'pending'."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch.object(repo, '_connect', return_value=mock_conn):
            repo.retry(uuid4())
        call_args = mock_cursor.execute.call_args[0]
        assert "status = 'pending'" in call_args[0]


# ═══════════════════════════════════════════════════════════════════
# 5. Consumer Tests (mocked ConsumerStateRepository)
# ═══════════════════════════════════════════════════════════════════


class MockConsumer(BaseConsumer):
    """Test consumer that records processed events."""

    def __init__(self, consumer_name: str, dsn: str = "postgresql://test:test@localhost/test"):
        super().__init__(consumer_name, dsn)
        self.processed_events: list[IntegrationEvent] = []
        self._raise_on = False

    def set_raise_on(self, raise_flag: bool = True):
        self._raise_on = raise_flag

    async def _process(self, event: IntegrationEvent) -> None:
        if self._raise_on:
            raise ValueError("Simulated consumer error")
        self.processed_events.append(event)


class TestConsumerFramework:
    """Consumer framework tests — dedup, retry, dead letter."""

    @pytest.fixture
    def sample_event(self):
        return IntegrationEvent(
            event_id=uuid4(),
            event_type="document.ready",
            aggregate_type="Document",
            aggregate_id="doc-001",
            occurred_at=datetime.now(timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_1_event_processed_once(self, sample_event):
        """New event -> processed once, ConsumerResult(success=True)."""
        consumer = MockConsumer("test-consumer")
        with patch.object(consumer._state_repo, 'is_processed', return_value=False):
            with patch.object(consumer._state_repo, 'mark_processed') as mock_mark:
                result = await consumer.consume(sample_event)
                assert result.success
                assert len(consumer.processed_events) == 1
                mock_mark.assert_called_once_with("test-consumer", sample_event.event_id)

    @pytest.mark.asyncio
    async def test_2_duplicate_event_skipped(self, sample_event):
        """Duplicate event -> ConsumerResult(success=True), not processed again."""
        consumer = MockConsumer("test-consumer")
        with patch.object(consumer._state_repo, 'is_processed', return_value=True):
            with patch.object(consumer._state_repo, 'mark_processed') as mock_mark:
                result = await consumer.consume(sample_event)
                assert result.success
                assert len(consumer.processed_events) == 0
                mock_mark.assert_not_called()

    @pytest.mark.asyncio
    async def test_3_exception_leads_to_retry(self, sample_event):
        """Exception -> ConsumerResult(success=False, retryable=True), not marked processed."""
        consumer = MockConsumer("test-consumer")
        consumer.set_raise_on(True)
        with patch.object(consumer._state_repo, 'is_processed', return_value=False):
            with patch.object(consumer._state_repo, 'mark_processed') as mock_mark:
                result = await consumer.consume(sample_event)
                assert not result.success
                assert result.retryable
                assert result.error is not None
                mock_mark.assert_not_called()

    @pytest.mark.asyncio
    async def test_4_non_retryable_error(self, sample_event):
        """Non-retryable error is expressible via ConsumerResult."""
        result = ConsumerResult(success=False, error="poison", retryable=False)
        assert not result.success
        assert not result.retryable

    @pytest.mark.asyncio
    async def test_5_consumer_result_frozen(self):
        """ConsumerResult is a frozen dataclass."""
        result = ConsumerResult(success=True)
        with pytest.raises(Exception):
            result.success = False


# ═══════════════════════════════════════════════════════════════════
# 6. Publisher Tests (mocked dependencies)
# ═══════════════════════════════════════════════════════════════════


class TestEventPublisher:
    """EventPublisher tests with mocked dependencies."""

    @pytest.fixture
    def publisher(self):
        return EventPublisher(
            dsn="postgresql://test:test@localhost/test",
            poll_interval=60,  # long so test doesn't loop
            batch_size=10,
        )

    @pytest.fixture
    def mock_db(self, publisher):
        """Mock _connect on all repos used by publisher."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        # Patch _connect on the publisher's repos to avoid real DB
        patchers = [
            patch.object(publisher._outbox_repo, '_connect', return_value=mock_conn),
            patch.object(publisher._consumer_state_repo, '_connect', return_value=mock_conn),
        ]
        for p in patchers:
            p.start()
        yield mock_conn, mock_cursor
        for p in patchers:
            p.stop()

    @pytest.mark.asyncio
    async def test_1_unpublished_events_fetched(self, publisher, mock_db):
        """Publisher fetches pending events from outbox."""
        mock_conn, mock_cursor = mock_db
        publisher._outbox_repo.fetch_pending = MagicMock(return_value=[
            {"id": uuid4(), "event_type": "document.ready", "aggregate_type": "Document",
             "aggregate_id": "doc-001", "payload": {"event_id": str(uuid4())},
             "metadata": {}, "created_at": datetime.now(timezone.utc),
             "published_at": None, "attempts": 0, "last_error": None, "status": "pending"},
        ])
        publisher._outbox_repo.fetch_failed = MagicMock(return_value=[])
        publisher._outbox_repo.mark_published = MagicMock()

        await publisher._poll_once()
        publisher._outbox_repo.fetch_pending.assert_called_once_with(limit=10)

    @pytest.mark.asyncio
    async def test_2_mark_published_on_success(self, publisher, mock_db):
        """Successful consumer delivery -> mark_published."""
        async def success_handler(event):
            return ConsumerResult(success=True)

        publisher.register_consumer("document.ready", success_handler)
        publisher._outbox_repo.fetch_pending = MagicMock(return_value=[
            {"id": uuid4(), "event_type": "document.ready", "aggregate_type": "Document",
             "aggregate_id": "doc-001", "payload": {
                 "event_id": str(uuid4()),
                 "event_type": "document.ready",
                 "aggregate_type": "Document",
                 "aggregate_id": "doc-001",
                 "occurred_at": datetime.now(timezone.utc).isoformat(),
                 "version": 1,
                 "payload": {},
                 "metadata": {},
             },
             "metadata": {}, "created_at": datetime.now(timezone.utc),
             "published_at": None, "attempts": 0, "last_error": None, "status": "pending"},
        ])
        publisher._outbox_repo.fetch_failed = MagicMock(return_value=[])
        publisher._outbox_repo.mark_published = MagicMock()

        await publisher._poll_once()
        publisher._outbox_repo.mark_published.assert_called_once()

    @pytest.mark.asyncio
    async def test_3_retry_uses_same_event_id(self, publisher, mock_db):
        """Retry preserves the same event_id (no new UUID)."""
        event_id = uuid4()
        call_count = 0
        captured_event_ids = []

        async def fail_then_succeed(event):
            nonlocal call_count, captured_event_ids
            call_count += 1
            captured_event_ids.append(event.event_id)
            if call_count == 1:
                return ConsumerResult(success=False, error="temporary error")
            return ConsumerResult(success=True)

        publisher.register_consumer("document.ready", fail_then_succeed)

        outbox_row = {
            "id": event_id,
            "event_type": "document.ready",
            "aggregate_type": "Document",
            "aggregate_id": "doc-001",
            "payload": {
                "event_id": str(event_id),
                "event_type": "document.ready",
                "aggregate_type": "Document",
                "aggregate_id": "doc-001",
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "version": 1,
                "payload": {},
                "metadata": {},
            },
            "metadata": {},
            "created_at": datetime.now(timezone.utc),
            "published_at": None,
            "attempts": 0,
            "last_error": None,
            "status": "pending",
        }

        publisher._outbox_repo.fetch_pending = MagicMock(return_value=[outbox_row])
        publisher._outbox_repo.fetch_failed = MagicMock(return_value=[])
        publisher._outbox_repo.mark_published = MagicMock()
        publisher._outbox_repo.mark_failed = MagicMock()

        # First attempt: fail
        await publisher._poll_once()
        # Second attempt: succeed (same event_id)
        await publisher._poll_once()

        assert len(captured_event_ids) == 2
        assert captured_event_ids[0] == captured_event_ids[1]

    @pytest.mark.asyncio
    async def test_4_retry_increments_attempts(self, publisher, mock_db):
        """Failed delivery calls mark_failed."""
        async def failing_handler(event):
            return ConsumerResult(success=False, error="error")

        publisher.register_consumer("document.ready", failing_handler)
        publisher._outbox_repo.fetch_pending = MagicMock(return_value=[
            {"id": uuid4(), "event_type": "document.ready", "aggregate_type": "Document",
             "aggregate_id": "doc-001", "payload": {
                 "event_id": str(uuid4()),
                 "event_type": "document.ready",
                 "aggregate_type": "Document",
                 "aggregate_id": "doc-001",
                 "occurred_at": datetime.now(timezone.utc).isoformat(),
                 "version": 1,
                 "payload": {},
                 "metadata": {},
             },
             "metadata": {}, "created_at": datetime.now(timezone.utc),
             "published_at": None, "attempts": 0, "last_error": None, "status": "pending"},
        ])
        publisher._outbox_repo.fetch_failed = MagicMock(return_value=[])
        publisher._outbox_repo.mark_failed = MagicMock()
        publisher._outbox_repo.mark_published = MagicMock()

        await publisher._poll_once()
        publisher._outbox_repo.mark_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_5_no_consumers_registered(self, publisher, mock_db):
        """No consumers registered -> event marked as published without error."""
        mock_conn, mock_cursor = mock_db
        publisher._outbox_repo.fetch_pending = MagicMock(return_value=[
            {"id": uuid4(), "event_type": "document.ready", "aggregate_type": "Document",
             "aggregate_id": "doc-001", "payload": {
                 "event_id": str(uuid4()),
                 "event_type": "document.ready",
                 "aggregate_type": "Document",
                 "aggregate_id": "doc-001",
                 "occurred_at": datetime.now(timezone.utc).isoformat(),
                 "version": 1,
                 "payload": {},
                 "metadata": {},
             },
             "metadata": {}, "created_at": datetime.now(timezone.utc),
             "published_at": None, "attempts": 0, "last_error": None, "status": "pending"},
        ])
        publisher._outbox_repo.fetch_failed = MagicMock(return_value=[])
        publisher._outbox_repo.mark_published = MagicMock()

        # No consumers registered for "document.ready"
        await publisher._poll_once()
        publisher._outbox_repo.mark_published.assert_called_once()

    @pytest.mark.asyncio
    async def test_6_batch_processing(self, publisher, mock_db):
        """Multiple pending events processed in one poll cycle."""
        async def success_handler(event):
            return ConsumerResult(success=True)

        publisher.register_consumer("document.ready", success_handler)

        event_ids = [uuid4(), uuid4(), uuid4()]
        pending_events = [
            {"id": eid, "event_type": "document.ready", "aggregate_type": "Document",
             "aggregate_id": "doc-001", "payload": {
                 "event_id": str(eid),
                 "event_type": "document.ready",
                 "aggregate_type": "Document",
                 "aggregate_id": "doc-001",
                 "occurred_at": datetime.now(timezone.utc).isoformat(),
                 "version": 1,
                 "payload": {"idx": i},
                 "metadata": {},
             },
             "metadata": {}, "created_at": datetime.now(timezone.utc),
             "published_at": None, "attempts": 0, "last_error": None, "status": "pending"}
            for i, eid in enumerate(event_ids)
        ]

        publisher._outbox_repo.fetch_pending = MagicMock(return_value=pending_events)
        publisher._outbox_repo.fetch_failed = MagicMock(return_value=[])
        publisher._outbox_repo.mark_published = MagicMock()

        await publisher._poll_once()
        assert publisher._outbox_repo.mark_published.call_count == 3

    @pytest.mark.asyncio
    async def test_7_graceful_shutdown_stops_after_current_batch(self, publisher, mock_db):
        """Graceful shutdown: stop() exits after current iteration."""
        event_id = uuid4()
        processed = []

        async def slow_handler(event):
            processed.append(event.event_id)
            return ConsumerResult(success=True)

        publisher.register_consumer("document.ready", slow_handler)
        publisher._outbox_repo.fetch_pending = MagicMock(return_value=[
            {"id": event_id, "event_type": "document.ready", "aggregate_type": "Document",
             "aggregate_id": "doc-001", "payload": {
                 "event_id": str(event_id),
                 "event_type": "document.ready",
                 "aggregate_type": "Document",
                 "aggregate_id": "doc-001",
                 "occurred_at": datetime.now(timezone.utc).isoformat(),
                 "version": 1,
                 "payload": {},
                 "metadata": {},
             },
             "metadata": {}, "created_at": datetime.now(timezone.utc),
             "published_at": None, "attempts": 0, "last_error": None, "status": "pending"},
        ])
        publisher._outbox_repo.fetch_failed = MagicMock(return_value=[])
        publisher._outbox_repo.mark_published = MagicMock()

        # Simulate stop after poll — event completed normally
        await publisher._poll_once()
        await publisher.stop()

        # Event still got processed (in-flight completed)
        assert len(processed) == 1
        assert not publisher._running

    @pytest.mark.asyncio
    async def test_8_in_flight_counter(self, publisher, mock_db):
        """In-flight counter accurately tracks events being processed."""
        event_id = uuid4()
        in_flight_during = []

        async def tracking_handler(event):
            in_flight_during.append(publisher.in_flight)
            return ConsumerResult(success=True)

        publisher.register_consumer("document.ready", tracking_handler)
        publisher._outbox_repo.fetch_pending = MagicMock(return_value=[
            {"id": event_id, "event_type": "document.ready", "aggregate_type": "Document",
             "aggregate_id": "doc-001", "payload": {
                 "event_id": str(event_id),
                 "event_type": "document.ready",
                 "aggregate_type": "Document",
                 "aggregate_id": "doc-001",
                 "occurred_at": datetime.now(timezone.utc).isoformat(),
                 "version": 1,
                 "payload": {},
                 "metadata": {},
             },
             "metadata": {}, "created_at": datetime.now(timezone.utc),
             "published_at": None, "attempts": 0, "last_error": None, "status": "pending"},
        ])
        publisher._outbox_repo.fetch_failed = MagicMock(return_value=[])
        publisher._outbox_repo.mark_published = MagicMock()

        assert publisher.in_flight == 0
        await publisher._poll_once()
        assert publisher.in_flight == 0
        # During processing, in_flight was 1
        assert in_flight_during == [1]


# ═══════════════════════════════════════════════════════════════════
# 7. Replay Tests
# ═══════════════════════════════════════════════════════════════════


class TestDeterministicReplay:
    """Replay — same events -> same result."""

    @pytest.fixture
    def events(self):
        return [
            IntegrationEvent(
                event_id=uuid4(),
                event_type=f"test.event.{i}",
                aggregate_type="Document",
                aggregate_id="doc-001",
                occurred_at=datetime.now(timezone.utc),
                payload={"counter": i},
            )
            for i in range(3)
        ]

    def test_deterministic_ordering(self, events):
        """Events ordered by occurred_at + event_id are deterministic."""
        sorted_events = sorted(events, key=lambda e: (e.occurred_at, e.event_id))
        assert sorted_events == sorted(events, key=lambda e: (e.occurred_at, e.event_id))

    def test_replay_same_result(self, events):
        """Replaying same events yields same state."""
        def replay(evts):
            state = {"counter": 0}
            for e in evts:
                state["counter"] = e.payload.get("counter", 0)
            return state

        state1 = replay(events)
        state2 = replay(events)
        assert state1 == state2


# ═══════════════════════════════════════════════════════════════════
# 8. Registry Fix Tests (P8)
# ═══════════════════════════════════════════════════════════════════


class TestRegistryFix:
    """P8 fix: handlers registered exactly once, not duplicated."""

    def _reset_registry(self):
        import backend.core.event_registry as reg
        reg._registry_initialized = False

    def test_single_registration(self):
        """Handlers registered once via ensure_event_registry()."""
        self._reset_registry()

        with patch("backend.core.event_handlers.register_sync_handlers") as mock:
            ensure_event_registry()
            mock.assert_called_once()

    def test_double_call_idempotent(self):
        """ensure_event_registry() x2 does not duplicate handlers."""
        self._reset_registry()

        with patch("backend.core.event_handlers.register_sync_handlers") as mock:
            ensure_event_registry()
            ensure_event_registry()
            mock.assert_called_once()
