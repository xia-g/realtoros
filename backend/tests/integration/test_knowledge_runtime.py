"""Integration tests for Knowledge Runtime Integration — consumer, pipeline, idempotency.

Tests cover:
  - Happy path: document.ready → GraphNode created + EmbeddingPipeline called
  - GraphSyncConsumer fix: session_factory + session passed to GraphLifecycleService
  - Idempotent replay: same event → no duplicate GraphNode, no duplicate Embedding
  - Partial failure: Graph sync ✅, Embedding ❌ → retryable error
  - Document not found → graceful skip
"""

from __future__ import annotations

import sys
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from backend.core.integration_event import IntegrationEvent
from backend.infrastructure.consumer_base import ConsumerResult
from backend.infrastructure.consumers.knowledge_runtime_consumer import (
    KnowledgeRuntimeConsumer,
)
from backend.services.knowledge_runtime.payload import DocumentReadyPayload


# ═══════════════════════════════════════════════════════════════════
# 1. KnowledgeRuntimeConsumer Integration Tests (mocked dependencies)
# ═══════════════════════════════════════════════════════════════════


class TestKnowledgeRuntimeConsumerIntegration:
    """KnowledgeRuntimeConsumer integration tests with mocked session and repos."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.execute = AsyncMock()
        session.get = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def mock_session_factory(self, mock_session):
        """Create a mock session factory that returns the same session twice."""
        factory = MagicMock()
        factory.return_value = mock_session
        return factory

    @pytest.fixture
    def consumer(self, mock_session_factory):
        """Create a consumer with mocked deps."""
        c = KnowledgeRuntimeConsumer(
            dsn="postgresql://test:***@localhost/test",
            session_factory=mock_session_factory,
        )
        return c

    @pytest.fixture
    def sample_event(self):
        """Create a sample document.ready IntegrationEvent."""
        return IntegrationEvent(
            event_id=uuid4(),
            event_type="document.ready",
            aggregate_type="Document",
            aggregate_id="doc-001",
            occurred_at=datetime.now(timezone.utc),
            payload={
                "document_id": str(uuid4()),
                "profile": {
                    "status": "READY",
                    "sections": {
                        "property": {
                            "cadastral_number": "78:01:0001001:1234",
                        },
                    },
                },
            },
        )

    @pytest.mark.asyncio
    async def test_happy_path_graph_node_created(self, consumer, sample_event, mock_session):
        """Happy path: document.ready → GraphNode created via service."""
        # Mock dedup
        with patch.object(consumer._state_repo, "is_processed", return_value=False):
            with patch.object(consumer._state_repo, "mark_processed") as mock_mark:
                # Mock document found
                mock_doc = MagicMock()
                mock_doc.id = uuid4()
                mock_doc.title = "Test Document"

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_doc
                mock_session.execute.return_value = mock_result

                # Mock GraphLifecycleService
                with patch(
                    "backend.services.knowledge_runtime.service.GraphLifecycleService"
                ) as mock_svc_cls:
                    mock_svc = MagicMock()
                    mock_svc.sync_entity = AsyncMock()
                    mock_svc_cls.return_value = mock_svc

                    # Mock EmbeddingPipeline
                    with patch(
                        "backend.services.knowledge_runtime.service.EmbeddingPipeline"
                    ) as mock_pipeline_cls:
                        mock_pipeline = MagicMock()
                        mock_pipeline.embed_chunks = AsyncMock(return_value=3)
                        mock_pipeline_cls.return_value = mock_pipeline

                        # Process the event
                        result = await consumer.consume(sample_event)

                        # Verify success
                        assert result.success
                        assert result.error is None
                        assert result.retryable

                        # Verify dedup was marked
                        mock_mark.assert_called_once_with(
                            consumer.consumer_name, sample_event.event_id
                        )

                        # Verify graph sync was called
                        mock_svc.sync_entity.assert_called_once()
                        call_kwargs = mock_svc.sync_entity.call_args[1]
                        assert call_kwargs["entity_type"] == "document"
                        assert "profile" in call_kwargs["metadata"]

                        # Verify embedding pipeline was called
                        assert mock_pipeline.embed_chunks.called

    @pytest.mark.asyncio
    async def test_idempotent_replay(self, consumer, sample_event, mock_session):
        """Same event twice → second call skipped by dedup."""
        # Mock dedup: first call -> not processed, second call -> already processed
        is_processed_values = [False, True]

        with patch.object(
            consumer._state_repo, "is_processed", side_effect=is_processed_values
        ):
            with patch.object(
                consumer._state_repo, "mark_processed"
            ) as mock_mark:
                # Mock document
                mock_doc = MagicMock()
                mock_doc.id = uuid4()
                mock_doc.title = "Test Document"

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_doc
                mock_session.execute.return_value = mock_result

                with patch(
                    "backend.services.knowledge_runtime.service.GraphLifecycleService"
                ) as mock_svc_cls:
                    mock_svc = MagicMock()
                    mock_svc.sync_entity = AsyncMock()
                    mock_svc_cls.return_value = mock_svc

                    with patch(
                        "backend.services.knowledge_runtime.service.EmbeddingPipeline"
                    ) as mock_pipeline_cls:
                        mock_pipeline = MagicMock()
                        mock_pipeline.embed_chunks = AsyncMock(return_value=3)
                        mock_pipeline_cls.return_value = mock_pipeline

                        # First call — should process
                        result1 = await consumer.consume(sample_event)
                        assert result1.success

                        # Second call — should be skipped by dedup
                        result2 = await consumer.consume(sample_event)
                        assert result2.success

                        # Verify service.process was called only once
                        # (the second call was skipped before reaching _process)
                        assert mock_svc.sync_entity.call_count == 1

    @pytest.mark.asyncio
    async def test_partial_failure_embedding(
        self, consumer, sample_event, mock_session
    ):
        """Graph sync ✅, Embedding ❌ → ConsumerResult(success=False, retryable=True)."""
        with patch.object(consumer._state_repo, "is_processed", return_value=False):
            with patch.object(consumer._state_repo, "mark_processed") as mock_mark:
                # Mock document found
                mock_doc = MagicMock()
                mock_doc.id = uuid4()
                mock_doc.title = "Test Document"

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_doc
                mock_session.execute.return_value = mock_result

                with patch(
                    "backend.services.knowledge_runtime.service.GraphLifecycleService"
                ) as mock_svc_cls:
                    mock_svc = MagicMock()
                    mock_svc.sync_entity = AsyncMock()
                    mock_svc_cls.return_value = mock_svc

                    with patch(
                        "backend.services.knowledge_runtime.service.EmbeddingPipeline"
                    ) as mock_pipeline_cls:
                        mock_pipeline = MagicMock()
                        mock_pipeline.embed_chunks = AsyncMock(
                            side_effect=RuntimeError("Embedding model unavailable")
                        )
                        mock_pipeline_cls.return_value = mock_pipeline

                        # Process the event — should fail
                        result = await consumer.consume(sample_event)

                        # Verify failure
                        assert not result.success
                        assert result.retryable
                        assert "Embedding model unavailable" in (result.error or "")

                        # mark_processed should NOT be called
                        mock_mark.assert_not_called()

    @pytest.mark.asyncio
    async def test_document_not_found(
        self, consumer, sample_event, mock_session
    ):
        """Document not found → service returns gracefully, consumer succeeds."""
        with patch.object(consumer._state_repo, "is_processed", return_value=False):
            with patch.object(consumer._state_repo, "mark_processed") as mock_mark:
                # Mock document NOT found
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None
                mock_session.execute.return_value = mock_result

                with patch(
                    "backend.services.knowledge_runtime.service.GraphLifecycleService"
                ) as mock_svc_cls:
                    await consumer.consume(sample_event)

                    # Graph sync should NOT be called
                    mock_svc_cls.assert_not_called()


# ═══════════════════════════════════════════════════════════════════
# 2. GraphSyncConsumer Fix Tests
# ═══════════════════════════════════════════════════════════════════


class TestGraphSyncConsumerFix:
    """GraphSyncConsumer fix: session_factory is passed and session is created."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def mock_session_factory(self, mock_session):
        factory = MagicMock()
        factory.return_value = mock_session
        return factory

    @pytest.fixture
    def consumer(self, mock_session_factory):
        from backend.infrastructure.consumers.graph_sync_consumer import GraphSyncConsumer

        c = GraphSyncConsumer(
            dsn="postgresql://test:***@localhost/test",
            session_factory=mock_session_factory,
        )
        return c

    @pytest.fixture
    def sample_event(self):
        return IntegrationEvent(
            event_id=uuid4(),
            event_type="document.ready",
            aggregate_type="Document",
            aggregate_id="doc-001",
            occurred_at=datetime.now(timezone.utc),
            payload={"status": "READY", "document_id": "doc-001"},
        )

    @pytest.mark.asyncio
    async def test_session_passed_to_graph_service(
        self, consumer, sample_event, mock_session
    ):
        """Session is created and passed to GraphLifecycleService."""
        with patch.object(consumer._state_repo, "is_processed", return_value=False):
            with patch.object(consumer._state_repo, "mark_processed") as mock_mark:
                with patch(
                    "backend.services.graph_lifecycle_service.GraphLifecycleService"
                ) as mock_svc_cls:
                    mock_svc = MagicMock()
                    mock_svc.sync_entity = AsyncMock()
                    mock_svc_cls.return_value = mock_svc

                    result = await consumer.consume(sample_event)

                    assert result.success

                    # Verify GraphLifecycleService was created with the session
                    call_args, call_kwargs = mock_svc_cls.call_args
                    # session=session keyword arg
                    assert "session" in call_kwargs
                    assert call_kwargs["session"] is mock_session

                    # Verify sync_entity was called with metadata (payload)
                    sync_call_kwargs = mock_svc.sync_entity.call_args[1]
                    assert "metadata" in sync_call_kwargs
                    assert sync_call_kwargs["metadata"] == sample_event.payload

                    # Verify session.commit was called
                    mock_session.commit.assert_called_once()

                    mock_mark.assert_called_once_with(
                        consumer.consumer_name, sample_event.event_id
                    )

    @pytest.mark.asyncio
    async def test_session_factory_used(
        self, consumer, sample_event, mock_session, mock_session_factory
    ):
        """session_factory() is called to create the session."""
        with patch.object(consumer._state_repo, "is_processed", return_value=False):
            with patch.object(consumer._state_repo, "mark_processed"):
                with patch(
                    "backend.services.graph_lifecycle_service.GraphLifecycleService"
                ) as mock_svc_cls:
                    mock_svc = MagicMock()
                    mock_svc.sync_entity = AsyncMock()
                    mock_svc_cls.return_value = mock_svc

                    await consumer.consume(sample_event)

                    # Verify session_factory was called
                    mock_session_factory.assert_called_once()
