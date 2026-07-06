"""
Accounting Binding — контракт JournalEntry.

Результат этапа Posting:
accounting_document → двойная проводка в главной книге.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from contracts.accounting_document import AccountingSide, DocumentStatus


class JournalLine(BaseModel):
    """Одна строка журнальной записи (дебет или кредит)."""
    line_id: str
    account_code: str
    side: AccountingSide
    amount: Decimal = Field(max_digits=16, decimal_places=2)
    dimension: str = ""
    description: str = ""
    sequence: int = Field(default=0, ge=0)


class PostingResult(str, Enum):
    """Результат разноски."""
    POSTED = "posted"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class JournalEntry(BaseModel):
    """Журнальная запись — результат разноски.

    Двойная запись: sum(debits) == sum(credits).
    Идемпотентна: повторная разноска того же accounting_document
    возвращает существующую запись (DUPLICATE).
    """
    schema_version: str = Field(default="1.0")
    entry_id: str
    accounting_document_id: str
    company_id: str = ""
    document_date: str  # ISO date

    # Проводки
    lines: list[JournalLine] = Field(default_factory=list)
    total_debit: Decimal = Field(default=Decimal("0"), max_digits=16, decimal_places=2)
    total_credit: Decimal = Field(default=Decimal("0"), max_digits=16, decimal_places=2)

    # Идемпотентность
    posting_hash: str = ""

    # Process state
    process_state: str = "completed"

    # Аудит
    posted_at: datetime | None = None
    posted_by: str = ""
    tracing_info: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True, "extra": "forbid"}
