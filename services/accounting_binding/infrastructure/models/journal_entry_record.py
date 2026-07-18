"""
Persistence Record — JournalEntry (SQLAlchemy).

UNIQUE(posting_hash) для идемпотентности.
Append-only: INSERT, не UPDATE.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SAEnum,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from contracts.journal_entry import PostingResult
from infrastructure.models.base import Base


class JournalEntryRecord(Base):
    """ORM-запись journal_entry (append-only)."""
    __tablename__ = "journal_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    accounting_document_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    document_date: Mapped[str] = mapped_column(String(10), default="")
    lines_json: Mapped[str] = mapped_column(Text, default="[]")
    total_debit: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    total_credit: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)

    # Idempotency — UNIQUE
    posting_hash: Mapped[str] = mapped_column(String(64), default="")

    # Process state
    process_state: Mapped[str] = mapped_column(String(20), default="completed")

    # Audit
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posted_by: Mapped[str] = mapped_column(String(64), default="")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("posting_hash", name="uq_journal_posting_hash"),
    )
