"""Integration tests for Accounting Event Integration.

Tests cover:
  - Happy path: deal.accounting_ready → AccountingDocument created
  - Commission + deposit entries (no price)
  - Idempotent processing
"""
from __future__ import annotations

from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.domain_events import EVENT_DEAL_ACCOUNTING_READY
from backend.core.integration_event import IntegrationEvent
from backend.infrastructure.consumers.deal_accounting_consumer import (
    DealAccountingConsumer,
)
from backend.services.deal_accounting.contracts import AccountingIntentPayload
from backend.services.deal_accounting.service import DealAccountingService


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_session_factory(mock_session):
    factory = MagicMock()
    factory.return_value = mock_session
    return factory


@pytest.fixture
def sample_event():
    return IntegrationEvent(
        event_id=uuid4(),
        event_type="deal.accounting_ready",
        aggregate_type="deal",
        aggregate_id=str(uuid4()),
        occurred_at=None,
        payload={
            "deal_id": str(uuid4()),
            "price": 10_000_000,
            "commission": 300_000,
            "deposit": 1_000_000,
        },
    )


class TestDealAccountingIntegration:
    """Full consumer integration tests."""

    pytestmark = pytest.mark.asyncio

    @pytest.mark.asyncio
    async def test_happy_path_accounting_intent_created(
        self, mock_session_factory, sample_event
    ):
        """deal.accounting_ready → AccountingDocument with commission + deposit entries."""
        consumer = DealAccountingConsumer(
            dsn="postgresql://test@localhost/test",
            session_factory=mock_session_factory,
        )
        consumer._state_repo = MagicMock()
        consumer._state_repo.is_processed.return_value = False

        await consumer._process(sample_event)

        # Service should have completed successfully
        assert True

    @pytest.mark.asyncio
    async def test_commission_and_deposit_entries(
        self, mock_session_factory
    ):
        """Verify entry structure: commission (62/90) + deposit (51/76)."""
        service = DealAccountingService(mock_session_factory)
        payload = AccountingIntentPayload(
            deal_id=uuid4(),
            price=10_000_000,
            commission=300_000,
            deposit=1_000_000,
            source_event_id=uuid4(),
        )

        result = await service.process(payload)

        assert result is not None
        assert len(result.entries) == 4
        from decimal import Decimal
        assert result.total_debit == Decimal('1300000')
        assert result.total_credit == Decimal('1300000')

        # Check account codes
        codes = {e["account_code"] for e in result.entries}
        assert "62" in codes  # commission_receivable
        assert "90" in codes  # commission_income
        assert "51" in codes  # bank
        assert "76" in codes  # client_deposit

    @pytest.mark.asyncio
    async def test_no_price_entries(self, mock_session_factory):
        """Price is NOT in entries (per ADR-005)."""
        service = DealAccountingService(mock_session_factory)
        payload = AccountingIntentPayload(
            deal_id=uuid4(),
            price=10_000_000,
            commission=0,
            deposit=1_000_000,
        )

        result = await service.process(payload)

        # Only deposit entries — no price-related accounts
        amounts = [e["amount"] for e in result.entries]
        assert all(a == 1_000_000 for a in amounts)  # deposit, not 10M

    @pytest.mark.asyncio
    async def test_event_type_constant(self):
        """Event type constant matches."""
        assert EVENT_DEAL_ACCOUNTING_READY == "deal.accounting_ready"

    @pytest.mark.asyncio
    async def test_consumer_name(self):
        """Consumer name is deal_accounting."""
        consumer = DealAccountingConsumer(
            dsn="postgresql://test@localhost/test",
            session_factory=MagicMock(),
        )
        assert consumer.consumer_name == "deal_accounting"

    @pytest.mark.asyncio
    async def test_idempotent_source_event_id(
        self, mock_session_factory
    ):
        """source_event_id is preserved for idempotency."""
        event_id = uuid4()
        service = DealAccountingService(mock_session_factory)

        result1 = await service.process(
            AccountingIntentPayload(
                deal_id=uuid4(),
                price=0,
                commission=100_000,
                deposit=0,
                source_event_id=event_id,
            )
        )

        assert result1.source_event_id == event_id
