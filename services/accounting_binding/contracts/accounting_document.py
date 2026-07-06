"""
Accounting Binding — контракт AccountingDocument.

Результат этапа Accounting Mapping:
enriched_document → учетный документ с разнесением по счетам.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from contracts.normalized_document import DocumentType


class AccountingSide(str, Enum):
    """Сторона проводки."""
    DEBIT = "debit"
    CREDIT = "credit"


class AccountEntry(BaseModel):
    """Бухгалтерская запись (одна строка проводки)."""
    account_code: str  # План счетов: 08, 19, 60, 68...
    side: AccountingSide
    amount: Decimal = Field(max_digits=16, decimal_places=2)
    dimension: str = ""  # Аналитика: контрагент, договор, объект
    description: str = ""
    sequence: int = Field(default=0, ge=0)


class TaxEntry(BaseModel):
    """Налоговая запись."""
    tax_code: str  # vat_20, vat_10, vat_0, vat_none
    tax_rate: Decimal = Field(max_digits=5, decimal_places=2)
    taxable_amount: Decimal = Field(max_digits=16, decimal_places=2)
    tax_amount: Decimal = Field(max_digits=16, decimal_places=2)


class DocumentStatus(str, Enum):
    """Статусы жизненного цикла учётного документа (domain state)."""
    DRAFT = "draft"
    READY = "ready"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"
    POSTED = "posted"


class ProcessingState(str, Enum):
    """Статус выполнения процесса (process state).
    
    Отдельно от domain state — иначе нельзя отличить:
    - документ APPROVED, но post не выполнился
    - replay идёт, но документ уже POSTED
    """
    PENDING = "pending"
    RUNNING = "running"
    FAILED = "failed"
    COMPLETED = "completed"
    REPLAYING = "replaying"


class ApprovalRequired(str, Enum):
    """Требуется ли approval для posting."""
    AUTO = "auto"
    REQUIRED = "required"
    OVERRIDDEN = "overridden"


class AccountingDocument(BaseModel):
    """Учётный документ — результат Accounting Mapping.

    Содержит всё необходимое для формирования проводок.
    Идемпотентен: повторное преобразование enriched_document
    с теми же правилами даёт тот же accounting_document.
    """
    schema_version: str = Field(default="1.0")
    document_id: str
    trace_id: str = ""
    source: str = ""
    document_type: DocumentType

    # Привязка к enriched_document
    enriched_document_id: str = ""
    company_id: str = ""
    document_date: date

    # Проводки
    entries: list[AccountEntry] = Field(default_factory=list)
    tax_entries: list[TaxEntry] = Field(default_factory=list)
    total_debit: Decimal = Field(default=Decimal("0"), max_digits=16, decimal_places=2)
    total_credit: Decimal = Field(default=Decimal("0"), max_digits=16, decimal_places=2)

    # Идемпотентность
    mapping_hash: str = ""

    # Revision для защиты stale approvals
    approval_revision: int = Field(default=0, ge=0)
    approved_mapping_hash: str = ""

    # Статус
    status: DocumentStatus = DocumentStatus.DRAFT
    process_state: ProcessingState = ProcessingState.PENDING
    approval_required: ApprovalRequired = ApprovalRequired.AUTO

    model_config = {"frozen": True, "extra": "forbid"}
