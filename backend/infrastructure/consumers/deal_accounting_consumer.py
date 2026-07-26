"""DealAccountingConsumer — consumes deal.accounting_ready → creates accounting intent.

Phase 1: creates AccountingDocument in READY status with commission + deposit entries.
Per ADR-004: posting (JournalEntry creation) is deferred to Phase 2.

Key design points:
  - Extends BaseConsumer — inherits idempotent dedup via ConsumerStateRepository
  - Uses SQLAlchemy async session (consistent with DealService pattern)
  - Delegates to DealAccountingService for intent creation
  - Business-level idempotency: (deal_id, source_type) check before insert
  - Consumer-level dedup: inherited from BaseConsumer
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker
from structlog import get_logger

from backend.core.integration_event import IntegrationEvent
from backend.infrastructure.consumer_base import (
    BaseConsumer,
    ConsumerResult,
)
from backend.services.deal_accounting.contracts import AccountingIntentPayload

logger = get_logger(__name__)


class DealAccountingConsumer(BaseConsumer):
    """Consumes deal.accounting_ready → creates AccountingDocument (READY).

    Two-layer idempotency:
      1. Consumer-level (inherited): ConsumerStateRepository by (consumer_name, event_id)
      2. Business-level (DealAccountingService): (deal_id, source_type) check

    Non-retryable errors (returns success=True):
      - Missing deal_id in payload
      - Deal not found in DB

    Retryable errors (returns success=False, retryable=True):
      - DB connection failure
      - Unexpected exceptions from DealAccountingService
    """

    consumer_name = "deal_accounting"

    def __init__(
        self,
        dsn: str,
        session_factory: async_sessionmaker,
    ) -> None:
        super().__init__(consumer_name=self.consumer_name, dsn=dsn)
        self._session_factory = session_factory
        # Lazy import to avoid circular dependency at module level
        self._service = None

    @property
    def service(self):
        if self._service is None:
            from backend.services.deal_accounting.service import (
                DealAccountingService,
            )

            self._service = DealAccountingService(self._session_factory)
        return self._service

    async def _process(self, event: IntegrationEvent) -> None:
        """Process a deal.accounting_ready event.

        Args:
            event: IntegrationEvent with payload containing
                   deal_id, price, commission, deposit_amount.

        Raises:
            Exception: Any non-handled error - consumer_base handles retry.
        """
        payload = event.payload

        # 1. Extract deal_id
        deal_id_str = payload.get("deal_id")
        if not deal_id_str:
            logger.error(
                "deal_accounting_missing_deal_id",
                event_id=str(event.event_id),
            )
            return

        deal_id = UUID(str(deal_id_str))
        logger.info(
            "deal_accounting_processing",
            deal_id=str(deal_id),
            event_id=str(event.event_id),
        )

        # 2. Map payload to AccountingIntentPayload
        intent_payload = AccountingIntentPayload(
            deal_id=deal_id,
            price=float(payload.get("price", 0)),
            currency=payload.get("price_currency", "RUB"),
            commission=float(payload.get("commission", 0)),
            deposit=float(payload.get("deposit_amount", 0)),
            source_event_id=event.event_id,
        )

        # 3. Delegate to DealAccountingService
        doc = await self.service.process(intent_payload)

        if doc is not None:
            logger.info(
                "deal_accounting_intent_created",
                deal_id=str(deal_id),
                document_id=doc.document_id,
                total_debit=str(doc.total_debit),
                total_credit=str(doc.total_credit),
                entries_count=len(doc.entries),
            )
        else:
            logger.info(
                "deal_accounting_intent_skipped_idempotent",
                deal_id=str(deal_id),
            )
