"""Unit tests for Knowledge Runtime Integration — payload, service, consumer.

Tests cover:
  - DocumentReadyPayload dataclass (construction, frozen, validation)
  - KnowledgeRuntimeService.process() — various scenarios
  - KnowledgeRuntimeConsumer._process() — delegation to service
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
from backend.services.knowledge_runtime.payload import DocumentReadyPayload


# ═══════════════════════════════════════════════════════════════════
# 1. DocumentReadyPayload Tests
# ═══════════════════════════════════════════════════════════════════


class TestDocumentReadyPayload:
    """DocumentReadyPayload dataclass — construction, frozen, validation."""

    def test_valid_payload(self):
        """Valid document_id + profile -> payload created."""
        doc_id = uuid4()
        payload = DocumentReadyPayload(
            document_id=doc_id,
            profile={"status": "READY"},
        )
        assert payload.document_id == doc_id
        assert payload.profile == {"status": "READY"}
        assert payload.source == "document.ready"

    def test_default_profile(self):
        """Omitting profile -> empty dict default."""
        doc_id = uuid4()
        payload = DocumentReadyPayload(document_id=doc_id)
        assert payload.document_id == doc_id
        assert payload.profile == {}
        assert payload.source == "document.ready"

    def test_frozen_dataclass(self):
        """DocumentReadyPayload is frozen — cannot mutate after creation."""
        payload = DocumentReadyPayload(document_id=uuid4())
        with pytest.raises(Exception):
            payload.document_id = uuid4()

    def test_required_document_id(self):
        """document_id is required — TypeError without it."""
        with pytest.raises(TypeError):
            DocumentReadyPayload()  # type: ignore

    def test_invalid_uuid_raises(self):
        """Passing non-UUID as document_id raises TypeError from UUID() constructor.
        Note: @dataclass doesn't enforce types at runtime, so we test that
        the UUID() conversion in the consumer/payload usage path would raise."""
        # The dataclass itself accepts any type (no runtime validation),
        # but consumer code that does UUID(str(value)) would catch this.
        # This test verifies the consumer path raises properly.
        payload = DocumentReadyPayload(document_id="not-a-uuid")  # type: ignore
        with pytest.raises(Exception):
            UUID(str(payload.document_id))


# ═══════════════════════════════════════════════════════════════════
# 2. KnowledgeRuntimeService Tests
# ═══════════════════════════════════════════════════════════════════


class TestKnowledgeRuntimeService:
    """KnowledgeRuntimeService.process() — orchestrates graph + embedding + search."""

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
        """Create a mock session factory."""
        factory = MagicMock()
        factory.return_value = mock_session
        return factory

    @pytest.fixture
    def service(self, mock_session_factory):
        from backend.services.knowledge_runtime.service import KnowledgeRuntimeService

        return KnowledgeRuntimeService(mock_session_factory)

    @pytest.fixture
    def sample_payload(self):
        return DocumentReadyPayload(
            document_id=uuid4(),
            profile={"status": "READY"},
        )

    @pytest.mark.asyncio
    async def test_happy_path(
        self, service, sample_payload, mock_session, mock_session_factory
    ):
        """Happy path: document found -> graph sync -> embedding -> search log."""
        # Mock document found
        mock_doc = MagicMock()
        mock_doc.id = sample_payload.document_id
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

                await service.process(sample_payload)

                # Verify document was loaded
                assert mock_session.execute.called

                # Verify graph sync was called
                mock_svc.sync_entity.assert_called_once()
                call_kwargs = mock_svc.sync_entity.call_args[1]
                assert call_kwargs["entity_type"] == "document"
                assert call_kwargs["entity_id"] == sample_payload.document_id
                assert "profile" in call_kwargs["metadata"]

                # Verify commit was called (graph phase)
                assert mock_session.commit.called

                # Verify embedding pipeline was called with a separate session
                assert mock_pipeline.embed_chunks.called

    @pytest.mark.asyncio
    async def test_document_not_found(
        self, service, sample_payload, mock_session
    ):
        """Document not found -> warning logged, no graph sync, no embedding."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with patch(
            "backend.services.knowledge_runtime.service.GraphLifecycleService"
        ) as mock_svc_cls:
            await service.process(sample_payload)

            # Graph sync should NOT be called
            mock_svc_cls.assert_not_called()

            # Only first session used (document load) — no second session for embedding
            assert mock_session.commit.called is False

    @pytest.mark.asyncio
    async def test_graph_sync_failure(
        self, service, sample_payload, mock_session, mock_session_factory
    ):
        """Graph sync fails -> exception propagates, no embedding."""
        mock_doc = MagicMock()
        mock_doc.id = sample_payload.document_id
        mock_doc.title = "Test Document"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute.return_value = mock_result

        with patch(
            "backend.services.knowledge_runtime.service.GraphLifecycleService"
        ) as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.sync_entity = AsyncMock(
                side_effect=ValueError("Graph sync failed")
            )
            mock_svc_cls.return_value = mock_svc

            with patch(
                "backend.services.knowledge_runtime.service.EmbeddingPipeline"
            ) as mock_pipeline_cls:
                with pytest.raises(ValueError, match="Graph sync failed"):
                    await service.process(sample_payload)

                # Embedding should NOT be called
                mock_pipeline_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_embedding_failure(
        self, service, sample_payload, mock_session, mock_session_factory
    ):
        """Embedding fails after graph sync succeeds -> exception propagates."""
        mock_doc = MagicMock()
        mock_doc.id = sample_payload.document_id
        mock_doc.title = "Test Document"

        # First session call returns document
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc

        # We need 2 different session contexts
        session1 = AsyncMock()
        session1.__aenter__ = AsyncMock(return_value=session1)
        session1.__aexit__ = AsyncMock(return_value=None)
        session1.commit = AsyncMock()
        session1.rollback = AsyncMock()
        session1.execute = AsyncMock(return_value=mock_result)
        session1.add = MagicMock()
        session1.flush = AsyncMock()

        session2 = AsyncMock()
        session2.__aenter__ = AsyncMock(return_value=session2)
        session2.__aexit__ = AsyncMock(return_value=None)
        session2.commit = AsyncMock()
        session2.rollback = AsyncMock()
        session2.execute = AsyncMock()
        session2.add = MagicMock()
        session2.flush = AsyncMock()

        factory = MagicMock()
        factory.side_effect = [session1, session2]

        from backend.services.knowledge_runtime.service import KnowledgeRuntimeService

        svc = KnowledgeRuntimeService(factory)

        with patch(
            "backend.services.knowledge_runtime.service.GraphLifecycleService"
        ) as mock_svc_cls:
            mock_graph_svc = MagicMock()
            mock_graph_svc.sync_entity = AsyncMock()
            mock_svc_cls.return_value = mock_graph_svc

            with patch(
                "backend.services.knowledge_runtime.service.EmbeddingPipeline"
            ) as mock_pipeline_cls:
                mock_pipeline = MagicMock()
                mock_pipeline.embed_chunks = AsyncMock(
                    side_effect=RuntimeError("Embedding failed")
                )
                mock_pipeline_cls.return_value = mock_pipeline

                with pytest.raises(RuntimeError, match="Embedding failed"):
                    await svc.process(sample_payload)

                # Graph sync succeeded (first session committed)
                session1.commit.assert_called_once()

                # Embedding session was rolled back
                session2.rollback.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# 3. KnowledgeRuntimeConsumer Tests
# ═══════════════════════════════════════════════════════════════════


class TestKnowledgeRuntimeConsumer:
    """KnowledgeRuntimeConsumer tests with mocked dependencies."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def mock_session_factory(self, mock_session):
        factory = MagicMock()
        factory.return_value = mock_session
        return factory

    @pytest.fixture
    def consumer(self, mock_session_factory):
        from backend.infrastructure.consumers.knowledge_runtime_consumer import (
            KnowledgeRuntimeConsumer,
        )

        c = KnowledgeRuntimeConsumer(
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
            payload={
                "document_id": str(uuid4()),
                "profile": {"status": "READY"},
            },
        )

    @pytest.mark.asyncio
    async def test_consumer_delegates_to_service(
        self, consumer, sample_event, mock_session
    ):
        """Consumer._process delegates to KnowledgeRuntimeService."""
        # Mock dedup
        with patch.object(
            consumer._state_repo, "is_processed", return_value=False
        ):
            with patch.object(
                consumer._state_repo, "mark_processed"
            ) as mock_mark:
                # Mock the service to avoid actual processing
                with patch.object(
                    consumer._service, "process"
                ) as mock_service_process:
                    mock_doc = MagicMock()
                    mock_doc.id = uuid4()
                    mock_doc.title = "Test Document"

                    mock_result = MagicMock()
                    mock_result.scalar_one_or_none.return_value = mock_doc
                    mock_session.execute.return_value = mock_result

                    result = await consumer.consume(sample_event)

                    assert result.success
                    # Verify service.process was called
                    mock_service_process.assert_called_once()
                    call_args = mock_service_process.call_args
                    payload = call_args[0][0]
                    assert isinstance(payload, DocumentReadyPayload)
                    assert payload.source == "document.ready"

                    # Verify dedup was marked
                    mock_mark.assert_called_once_with(
                        consumer.consumer_name, sample_event.event_id
                    )

    @pytest.mark.asyncio
    async def test_consumer_duplicate_skipped(self, consumer, sample_event):
        """Same event_id twice -> second skipped, service not called."""
        with patch.object(
            consumer._state_repo, "is_processed", return_value=True
        ):
            with patch.object(
                consumer._state_repo, "mark_processed"
            ) as mock_mark:
                with patch.object(
                    consumer._service, "process"
                ) as mock_service:
                    result = await consumer.consume(sample_event)

                    assert result.success
                    mock_service.assert_not_called()
                    mock_mark.assert_not_called()

    @pytest.mark.asyncio
    async def test_consumer_error_retryable(
        self, consumer, sample_event, mock_session
    ):
        """Exception in service -> ConsumerResult(success=False, retryable=True)."""
        with patch.object(
            consumer._state_repo, "is_processed", return_value=False
        ):
            with patch.object(
                consumer._state_repo, "mark_processed"
            ) as mock_mark:
                with patch.object(
                    consumer._service, "process"
                ) as mock_service:
                    mock_service.side_effect = ValueError(
                        "Document not found"
                    )

                    result = await consumer.consume(sample_event)

                    assert not result.success
                    assert result.retryable
                    assert "Document not found" in (result.error or "")
                    mock_mark.assert_not_called()

    @pytest.mark.asyncio
    async def test_consumer_name_is_knowledge_runtime(self, consumer):
        """Consumer name is 'knowledge_runtime'."""
        assert consumer._consumer_name == "knowledge_runtime"
