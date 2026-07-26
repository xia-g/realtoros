"""Stream 1 — Accounting domain models."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any


class AccountType(str, Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class EntryStatus(str, Enum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    POSTED = "POSTED"
    LOCKED = "LOCKED"
    REJECTED = "REJECTED"


ENTRY_TRANSITIONS: dict[str, list[str]] = {
    "DRAFT": ["VALIDATED", "REJECTED"],
    "VALIDATED": ["POSTED", "DRAFT"],
    "POSTED": [],
    "LOCKED": [],
    "REJECTED": ["DRAFT"],
}


@dataclass
class Account:
    account_id: str
    code: str
    name: str
    account_type: AccountType
    parent_id: str | None = None
    is_active: bool = True


@dataclass
class AccountingPeriod:
    period_id: str
    name: str
    start_date: date
    end_date: date
    status: str = "OPEN"


@dataclass
class Journal:
    journal_id: str
    name: str
    journal_type: str
    period_id: str


@dataclass
class EntryLine:
    line_id: str
    entry_id: str = ""
    account_id: str = ""
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    counterparty_id: str | None = None
    description: str = ""


@dataclass
class AccountingEntry:
    entry_id: str
    journal_id: str = ""
    document_id: str = ""
    period_id: str = ""
    entry_date: date | None = None
    description: str = ""
    status: str = "DRAFT"
    lines: list[EntryLine] = field(default_factory=list)
    created_at: datetime | None = None
    posted_at: datetime | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def total_debit(self) -> Decimal:
        return sum((l.debit for l in self.lines), Decimal("0"))

    @property
    def total_credit(self) -> Decimal:
        return sum((l.credit for l in self.lines), Decimal("0"))

    @property
    def is_balanced(self) -> bool:
        return self.total_debit == self.total_credit
