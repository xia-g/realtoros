"""Unit tests for Accounting Event Integration — contracts, service, consumer."""
from __future__ import annotations

from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.domain_events import EVENT_DEAL_ACCOUNTING_READY
from backend.services.deal_accounting.contracts import (
    AccountingIntentPayload,
)
from backend.services.deal_accounting.service import (
    DealAccountingService,
    AccountingDocumentResult,
)
from backend.infrastructure.consumers.deal_accounting_consumer import (
    DealAccountingConsumer,
)


class TestEventContract:
    """EVENT_DEAL_ACCOUNTING_READY constant."""

    def test_event_type_value(self):
        assert EVENT_DEAL_ACCOUNTING_READY == "deal.accounting_ready"

    def test_event_is_string(self):
        assert isinstance(EVENT_DEAL_ACCOUNTING_READY, str)


class TestAccountingIntentPayload:
    """AccountingIntentPayload dataclass."""

    def test_valid_payload(self):
        deal_id = uuid4()
        payload = AccountingIntentPayload(
            deal_id=deal_id,
            price=10_000_000,
            commission=300_000,
            deposit=1_000_000,
            source_event_id=uuid4(),
        )
        assert payload.deal_id == deal_id
        assert payload.commission == 300_000
        assert payload.deposit == 1_000_000
        assert payload.currency == "RUB"

    def test_default_currency(self):
        payload = AccountingIntentPayload(deal_id=uuid4(), price=0)
        assert payload.currency == "RUB"

    def test_default_commission_deposit(self):
        payload = AccountingIntentPayload(deal_id=uuid4(), price=0)
        assert payload.commission == 0.0
        assert payload.deposit == 0.0
        assert payload.source_event_id is None


class TestAccountingDocumentResult:
    """AccountingDocumentResult dataclass."""

    def test_default_status(self):
        doc = AccountingDocumentResult(
            document_id=uuid4(),
            deal_id=uuid4(),
            source_event_id=uuid4(),
            source_type="deal.accounting_ready",
            total_debit=0,
            total_credit=0,
        )
        assert doc.status == "READY"
        assert doc.entries == []


class TestDealAccountingService:
    """DealAccountingService — orchestration tests with mocked session."""

    pytestmark = pytest.mark.asyncio

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.fixture
    def mock_session_factory(self, mock_session):
        factory = MagicMock()
        factory.return_value = mock_session
        return factory

    @pytest.fixture
    def service(self, mock_session_factory):
        return DealAccountingService(mock_session_factory)

    async def test_happy_path_commission_and_deposit(self, service, mock_session):
        """Happy path: creates intent with commission + deposit entries."""
        deal_id = uuid4()
        payload = AccountingIntentPayload(
            deal_id=deal_id,
            price=10_000_000,
            commission=300_000,
            deposit=1_000_000,
        )

        result = await service.process(payload)

        assert result is not None
        assert result.deal_id == deal_id
        assert result.source_type == "deal.accounting_ready"
        assert result.status == "READY"
        # Commission (2 entries) + Deposit (2 entries) = 4
        assert len(result.entries) == 4
        # Total = 300k + 1M
        assert result.total_debit == 1_300_000
        assert result.total_credit == 1_300_000

    async def test_commission_only(self, service, mock_session):
        """Only commission — 2 entries."""
        deal_id = uuid4()
        payload = AccountingIntentPayload(
            deal_id=deal_id,
            price=10_000_000,
            commission=300_000,
            deposit=0,
        )

        result = await service.process(payload)

        assert len(result.entries) == 2
        assert result.total_debit == 300_000
        assert result.total_credit == 300_000

    async def test_deposit_only(self, service, mock_session):
        """Only deposit — 2 entries."""
        deal_id = uuid4()
        payload = AccountingIntentPayload(
            deal_id=deal_id,
            price=10_000_000,
            commission=0,
            deposit=1_000_000,
        )

        result = await service.process(payload)

        assert len(result.entries) == 2
        assert result.total_debit == 1_000_000
        assert result.total_credit == 1_000_000

    async def test_no_commission_no_deposit(self, service, mock_session):
        """No financials — 0 entries, document still created."""
        deal_id = uuid4()
        payload = AccountingIntentPayload(
            deal_id=deal_id,
            price=10_000_000,
            commission=0,
            deposit=0,
        )

        result = await service.process(payload)

        assert result is not None
        assert len(result.entries) == 0

    async def test_commission_entry_structure(self, service, mock_session):
        """Commission entry has correct account codes."""
        payload = AccountingIntentPayload(
            deal_id=uuid4(),
            price=0,
            commission=100_000,
            deposit=0,
        )

        result = await service.process(payload)

        debit = result.entries[0]
        credit = result.entries[1]
        assert debit["account_code"] == "62"
        assert debit["side"] == "DEBIT"
        assert credit["account_code"] == "90"
        assert credit["side"] == "CREDIT"

    async def test_deposit_entry_structure(self, service, mock_session):
        """Deposit entry has correct account codes."""
        payload = AccountingIntentPayload(
            deal_id=uuid4(),
            price=0,
            commission=0,
            deposit=500_000,
        )

        result = await service.process(payload)

        debit = result.entries[0]
        credit = result.entries[1]
        assert debit["account_code"] == "51"
        assert debit["side"] == "DEBIT"
        assert credit["account_code"] == "76"
        assert credit["side"] == "CREDIT"

    async def test_no_price_entries(self, service, mock_session):
        """Price is NOT included in entries (per ADR-005)."""
        payload = AccountingIntentPayload(
            deal_id=uuid4(),
            price=10_000_000,  # price is high but should NOT create entries
            commission=100_000,
            deposit=0,
        )

        result = await service.process(payload)

        # Only commission entries — no price entries
        assert len(result.entries) == 2
        for entry in result.entries:
            assert entry["amount"] == 100_000  # commission, not 10M

    async def test_source_event_id_correlation(self, service, mock_session):
        """source_event_id is preserved in result."""
        event_id = uuid4()
        payload = AccountingIntentPayload(
            deal_id=uuid4(),
            price=0,
            commission=100_000,
            deposit=0,
            source_event_id=event_id,
        )

        result = await service.process(payload)

        assert result.source_event_id == event_id


class TestDealAccountingConsumer:
    """DealAccountingConsumer — orchestration layer (unit tests)."""

    pytestmark = pytest.mark.asyncio

    @pytest.fixture
    def mock_service(self):
        return AsyncMock()

    @pytest.fixture
    def consumer(self, mock_service):
        c = DealAccountingConsumer.__new__(DealAccountingConsumer)
        c._service = mock_service
        c._state_repo = MagicMock()
        c._state_repo.is_processed.return_value = False
        c.consumer_name = "deal_accounting"
        return c

    def test_consumer_name(self, consumer):
        assert consumer.consumer_name == "deal_accounting"

    async def test_process_happy_path(self, consumer, mock_service):
        """Consumer processes deal.accounting_ready event successfully."""
        from backend.core.integration_event import IntegrationEvent

        mock_service.process.return_value = MagicMock()

        event = IntegrationEvent(
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
        result = await consumer._process(event)
        assert result is None or getattr(result, 'success', True)

    async def test_wrong_event_type_handled_gracefully(self, consumer, mock_service):
        """Consumer doesn't validate event_type — registration guarantees it."""
        from backend.core.integration_event import IntegrationEvent

        # Event with wrong type but valid payload structure — consumer processes normally
        mock_service.process.return_value = MagicMock()

        event = IntegrationEvent(
            event_id=uuid4(),
            event_type="deal.updated",
            aggregate_type="deal",
            aggregate_id=str(uuid4()),
            occurred_at=None,
            payload={"deal_id": str(uuid4())},
        )
        # Should not raise — consumer processes any event with deal_id
        result = await consumer._process(event)
        assert result is None or getattr(result, 'success', True)

    async def test_service_error_bubbles_up(self, consumer, mock_service):
        """Service error propagates to caller."""
        from backend.core.integration_event import IntegrationEvent

        mock_service.process.side_effect = Exception("DB error")

        event = IntegrationEvent(
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
        with pytest.raises(Exception, match="DB error"):
            await consumer._process(event)
