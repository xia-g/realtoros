"""
Persistence Record — AccountingDocument (SQLAlchemy).

Отдельно от domain-модели (frozen Pydantic).
Domain ↔ Mapper ↔ Record.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from contracts.accounting_document import (
    ApprovalRequired,
    DocumentStatus,
    ProcessingState,
)
from infrastructure.models.base import Base


class AccountingDocumentRecord(Base):
    """ORM-запись accounting_document.

    Не frozen — SQLAlchemy управляет состоянием.
    Не Pydantic — чистая ORM.
    """
    __tablename__ = "accounting_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    document_date: Mapped[date] = mapped_column(Date, nullable=False)
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="")
    trace_id: Mapped[str] = mapped_column(String(64), default="")

    # Domain state
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, name="accounting_doc_status"),
        default=DocumentStatus.DRAFT, nullable=False,
    )
    process_state: Mapped[ProcessingState] = mapped_column(
        SAEnum(ProcessingState, name="accounting_doc_process_state"),
        default=ProcessingState.PENDING, nullable=False,
    )
    approval_required: Mapped[ApprovalRequired] = mapped_column(
        SAEnum(ApprovalRequired, name="accounting_doc_approval"),
        default=ApprovalRequired.AUTO, nullable=False,
    )

    # Entries (JSON — для простоты, в продакшене — отдельная таблица)
    entries_json: Mapped[str] = mapped_column(Text, default="[]")
    tax_entries_json: Mapped[str] = mapped_column(Text, default="[]")
    total_debit: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    total_credit: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)

    # Idempotency + Revision
    mapping_hash: Mapped[str] = mapped_column(String(32), default="", index=True)
    approval_revision: Mapped[int] = mapped_column(Integer, default=0)
    approved_mapping_hash: Mapped[str] = mapped_column(String(32), default="")

    # Correlation
    pipeline_run_id: Mapped[str] = mapped_column(String(36), default="")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # Поиск по хешу (idempotency)
        {"sqlite_autoincrement": True},
    )
