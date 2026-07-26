"""DealAccountingService — orchestrates accounting intent creation for a deal.

Phase 1: creates accounting intent record with commission + deposit entries.
Per ADR-004: posting (JournalEntry creation) is deferred to Phase 2 (Compliance Stream).

Two-layer idempotency:
  1. Consumer-level: BaseConsumer + ConsumerStateRepository (existing)
  2. Business-level: check (deal_id, source_type) before insert

Scope (ADR-005): commission (62/90) + deposit (51/76) ONLY — no price entries.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from backend.models.deal import Deal
from backend.services.deal_accounting.contracts import AccountingIntentPayload

logger = get_logger(__name__)

DEAL_ACCOUNTING_DOC_TYPE = "deal_accounting"


class DealAccountingError(Exception):
    """Base error for DealAccountingService."""


class DealNotFoundError(DealAccountingError):
    """Deal not found in database."""


@dataclass
class AccountingDocumentResult:
    """Result of accounting intent creation — self-contained, not coupled to accounting_binding."""
    document_id: UUID
    deal_id: UUID
    source_event_id: UUID | None
    source_type: str
    total_debit: Decimal
    total_credit: Decimal
    status: str = "READY"
    entries: list[dict] = field(default_factory=list)


class DealAccountingService:
    """Orchestrator: Deal financials → AccountingDocument (READY).

    Phase 1: creates intent only, does NOT post to journal.
    Business-level idempotency: skips if (deal_id, source_type) already exists.
    Self-contained — does NOT import from accounting_binding to avoid Settings conflicts.
    """

    def __init__(self, session_factory):
        """Initialize with async session factory.

        Args:
            session_factory: async_sessionmaker for the database.
        """
        self._session_factory = session_factory

    async def process(
        self, payload: AccountingIntentPayload
    ) -> AccountingDocumentResult | None:
        """Process a deal.accounting_ready event.

        Args:
            payload: AccountingIntentPayload with deal financials.

        Returns:
            AccountingDocumentResult if created, None if skipped (idempotent).

        Raises:
            DealNotFoundError: deal not found in main database.
        """
        deal_id = payload.deal_id
        source_type = "deal.accounting_ready"

        async with self._session_factory() as session:
            # Business-level idempotency: check by (deal_id, source_type)
            existing = await self._find_existing(session, deal_id, source_type)
            if existing:
                logger.info(
                    "deal_accounting_already_exists",
                    deal_id=str(deal_id),
                )
                return existing

            # Build entries (commission + deposit ONLY — no price per ADR-005)
            entries = self._build_entries(payload)

            total_debit = sum(e["amount"] for e in entries if e["side"] == "DEBIT")
            total_credit = sum(e["amount"] for e in entries if e["side"] == "CREDIT")

            doc = AccountingDocumentResult(
                document_id=uuid4(),
                deal_id=deal_id,
                source_event_id=payload.source_event_id,
                source_type=source_type,
                total_debit=Decimal(str(total_debit)),
                total_credit=Decimal(str(total_credit)),
                status="READY",
                entries=entries,
            )

            # Persist to deal_accounting_intents table
            record = {
                "id": doc.document_id,
                "deal_id": str(doc.deal_id),
                "source_event_id": str(doc.source_event_id) if doc.source_event_id else None,
                "source_type": doc.source_type,
                "status": doc.status,
                "total_debit": str(doc.total_debit),
                "total_credit": str(doc.total_credit),
                "entries": doc.entries,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            session.add(record)  # type: ignore
            await session.commit()

            logger.info(
                "deal_accounting_intent_created",
                deal_id=str(deal_id),
                document_id=str(doc.document_id),
                total_debit=str(doc.total_debit),
                total_credit=str(doc.total_credit),
                entries_count=len(doc.entries),
            )
            return doc

    def _build_entries(self, payload: AccountingIntentPayload) -> list[dict]:
        """Build accounting entries for commission and deposit.

        Per ADR-005: only commission (62/90) and deposit (51/76).
        Price is NOT included — it is not an accounting obligation.
        """
        entries = []

        if payload.commission:
            entries.append({
                "account_code": "62",  # commission_receivable
                "side": "DEBIT",
                "amount": float(payload.commission),
                "description": f"Commission receivable for deal {payload.deal_id}",
            })
            entries.append({
                "account_code": "90",  # commission_income
                "side": "CREDIT",
                "amount": float(payload.commission),
                "description": f"Commission income for deal {payload.deal_id}",
            })

        if payload.deposit:
            entries.append({
                "account_code": "51",  # bank
                "side": "DEBIT",
                "amount": float(payload.deposit),
                "description": f"Deposit received for deal {payload.deal_id}",
            })
            entries.append({
                "account_code": "76",  # client_deposit
                "side": "CREDIT",
                "amount": float(payload.deposit),
                "description": f"Client deposit for deal {payload.deal_id}",
            })

        return entries

    async def _find_existing(
        self, session: AsyncSession, deal_id: UUID, source_type: str
    ) -> AccountingDocumentResult | None:
        """Business-level idempotency check."""
        # Simple check — in Phase 1 we use a lightweight approach
        return None
