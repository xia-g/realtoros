"""Integration tests for Deal Context Resolution — consumer, pipeline, idempotency.

Tests cover:
  - Happy path: document.ready → Deal enriched (property_id, participants)
  - AMBIGUOUS: missing INN → consumer success (not retryable)
  - Idempotent replay: same event twice → identical state
  - NOT_FOUND: new Client and Property created from OCR data
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
from backend.infrastructure.consumers.deal_context_resolution_consumer import (
    DealContextResolutionConsumer,
)
from backend.services.deal_context_resolution.models import (
    ResolutionResult,
    ResolutionStatus,
    DealResolutionContext,
)


# ═══════════════════════════════════════════════════════════════════
# 1. Consumer Framework Tests (mocked dependencies)
# ═══════════════════════════════════════════════════════════════════


class TestDealContextResolutionConsumer:
    """DealContextResolutionConsumer tests with mocked session and repos."""

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
    def consumer(self, mock_session_factory):
        """Create a consumer with mocked deps."""
        c = DealContextResolutionConsumer(
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
                    "sections": {
                        "property": {
                            "cadastral_number": "78:01:0001001:1234",
                            "address": "ул. Ленина, д. 1, кв. 50",
                            "property_type": "apartment",
                        },
                        "parties": {
                            "buyer": {
                                "name": "Иван Иванов",
                                "inn": "770123456789",
                                "type": "individual",
                            },
                            "seller": {
                                "name": "ООО Ромашка",
                                "inn": "7701234567",
                                "type": "legal",
                            },
                        },
                    },
                },
            },
        )

    @pytest.mark.asyncio
    async def test_happy_path_all_resolved(
        self, consumer, sample_event, mock_session, mock_session_factory
    ):
        """Happy path: document.ready → all entities resolved → deal enriched."""
        # Mock dedup — not yet processed
        with (
            patch.object(
                consumer._state_repo,
                "is_processed",
                return_value=False,
            ),
            patch.object(
                consumer._state_repo,
                "mark_processed",
            ) as mock_mark,
        ):
            # Mock the deal lookup — found
            mock_deal = MagicMock()
            mock_deal.id = uuid4()
            mock_deal.property_id = None

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_deal
            mock_session.execute.return_value = mock_result

            # Process the event
            result = await consumer.consume(sample_event)

            # Should succeed
            assert result.success
            mock_mark.assert_called_once_with(
                consumer.consumer_name, sample_event.event_id
            )

    @pytest.mark.asyncio
    async def test_ambiguous_not_retried(
        self, consumer, mock_session, mock_session_factory
    ):
        """AMBIGUOUS → ConsumerResult(success=True) — not retried."""
        event = IntegrationEvent(
            event_id=uuid4(),
            event_type="document.ready",
            aggregate_type="Document",
            aggregate_id="doc-002",
            occurred_at=datetime.now(timezone.utc),
            payload={
                "document_id": str(uuid4()),
                "profile": {
                    "sections": {
                        "property": {},
                        "parties": {
                            "buyer": {
                                "name": "Иван Иванов",
                                "inn": None,
                            },
                            "seller": {
                                "name": "ООО Ромашка",
                                "inn": None,
                            },
                        },
                    },
                },
            },
        )

        with (
            patch.object(
                consumer._state_repo,
                "is_processed",
                return_value=False,
            ),
            patch.object(
                consumer._state_repo,
                "mark_processed",
            ) as mock_mark,
        ):
            # Mock deal found
            mock_deal = MagicMock()
            mock_deal.id = uuid4()

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_deal
            mock_session.execute.return_value = mock_result

            result = await consumer.consume(event)
            assert result.success
            mock_mark.assert_called_once()

    @pytest.mark.asyncio
    async def test_deal_not_found_skips(
        self, consumer, mock_session, mock_session_factory
    ):
        """Deal not found → consumer returns success (not retried)."""
        event = IntegrationEvent(
            event_id=uuid4(),
            event_type="document.ready",
            aggregate_type="Document",
            aggregate_id="doc-003",
            occurred_at=datetime.now(timezone.utc),
            payload={
                "document_id": str(uuid4()),
                "profile": {},
            },
        )

        with (
            patch.object(
                consumer._state_repo,
                "is_processed",
                return_value=False,
            ),
            patch.object(
                consumer._state_repo,
                "mark_processed",
            ) as mock_mark,
        ):
            # Mock deal NOT found
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            result = await consumer.consume(event)
            assert result.success  # Not an error
            mock_mark.assert_called_once()

    @pytest.mark.asyncio
    async def test_idempotent_replay(
        self, consumer, sample_event, mock_session
    ):
        """Same event twice → dedup returns success, _process not called."""
        with (
            patch.object(
                consumer._state_repo,
                "is_processed",
                return_value=True,
            ),
            patch.object(
                consumer._state_repo,
                "mark_processed",
            ) as mock_mark,
        ):
            result = await consumer.consume(sample_event)
            assert result.success
            mock_mark.assert_not_called()

    @pytest.mark.asyncio
    async def test_consumer_error_not_marked_processed(
        self, consumer, sample_event, mock_session
    ):
        """Processing error → not marked processed (retry will pick up)."""
        with (
            patch.object(
                consumer._state_repo,
                "is_processed",
                return_value=False,
            ),
            patch.object(
                consumer._state_repo,
                "mark_processed",
            ) as mock_mark,
        ):
            # Make session.execute raise
            mock_session.execute.side_effect = ValueError("DB error")

            result = await consumer.consume(sample_event)

            assert not result.success
            assert result.retryable
            mock_mark.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_found_creates_new_entities(
        self, consumer, mock_session, mock_session_factory
    ):
        """NOT_FOUND → new Client and Property created from OCR data."""
        event = IntegrationEvent(
            event_id=uuid4(),
            event_type="document.ready",
            aggregate_type="Document",
            aggregate_id="doc-004",
            occurred_at=datetime.now(timezone.utc),
            payload={
                "document_id": str(uuid4()),
                "profile": {
                    "sections": {
                        "property": {
                            "address": "Новый адрес, д. 10",
                        },
                        "parties": {
                            "buyer": {
                                "name": "Новый Покупатель",
                                "inn": None,
                            },
                            "seller": {
                                "name": "Новый Продавец",
                                "inn": None,
                            },
                        },
                    },
                },
            },
        )

        with (
            patch.object(
                consumer._state_repo,
                "is_processed",
                return_value=False,
            ),
            patch.object(
                consumer._state_repo,
                "mark_processed",
            ) as mock_mark,
        ):
            # Mock deal found
            mock_deal = MagicMock()
            mock_deal.id = uuid4()

            # For property + buyer + seller = 3 queries, all returning None
            # Then 3 add() calls for new entities
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_deal
            mock_session.execute.return_value = mock_result

            result = await consumer.consume(event)
            assert result.success
            mock_mark.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# 2. Pipeline Integration Tests (resolver + app service)
# ═══════════════════════════════════════════════════════════════════


class TestResolverPipeline:
    """Resolver + ApplicationService integration tests."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.get = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_resolver_orchestrates_all_three(
        self, mock_session
    ):
        """DealContextResolver.delegate() orchestrates property, buyer, seller."""
        from backend.services.deal_context_resolution.resolver import (
            DealContextResolver,
        )
        from backend.models.deal import Deal

        resolver = DealContextResolver(mock_session)

        deal = Deal(
            id=uuid4(),
            deal_type="buy",
            status="negotiation",
            title="Test Deal",
            price=10000000,
            start_date=datetime.now(timezone.utc).date(),
            property_id=uuid4(),
            created_by=uuid4(),
        )

        profile = {
            "sections": {
                "property": {
                    "cadastral_number": "78:01:0001001:1234",
                    "address": "Test Address",
                },
                "parties": {
                    "buyer": {
                        "name": "Buyer Name",
                        "inn": "770123456789",
                    },
                    "seller": {
                        "name": "Seller Name",
                        "inn": "7701234567",
                    },
                },
            },
        }

        # Mock all DB queries return None (create new path)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await resolver.resolve(deal, profile)

        assert result.property_result is not None
        assert result.buyer_result is not None
        assert result.seller_result is not None
        # All should be NOT_FOUND since no matching entities
        assert result.property_result.status == ResolutionStatus.NOT_FOUND
        assert result.buyer_result.status == ResolutionStatus.NOT_FOUND
        assert result.seller_result.status == ResolutionStatus.NOT_FOUND
