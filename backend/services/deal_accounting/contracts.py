"""DealAccounting — contracts for accounting intent creation.

Phase 1: simple frozen dataclasses for commission + deposit entries.
These are internal contracts — translated to AccountingBinding's Pydantic models
by DealAccountingService before persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class AccountingIntentPayload:
    """Payload extracted from deal.accounting_ready event.

    Contains the financial data needed to create accounting entries.
    """

    deal_id: UUID
    price: float = 0.0
    currency: str = "RUB"
    commission: float = 0.0
    deposit: float = 0.0
    source_event_id: UUID | None = None


@dataclass(frozen=True)
class CommissionEntry:
    """Commission accrual: Дт 62 (commission_receivable) / Кт 90 (commission_income).

    Per ADR-005: posting scope includes commission ONLY (not price).
    """

    account_debit: str = "62"
    account_credit: str = "90"
    amount: float = 0.0
    description: str = ""


@dataclass(frozen=True)
class DepositEntry:
    """Deposit tracking: Дт 51 (bank) / Кт 76 (client_deposit).

    Per ADR-005: posting scope includes deposit ONLY (not price).
    """

    account_debit: str = "51"
    account_credit: str = "76"
    amount: float = 0.0
    description: str = ""
