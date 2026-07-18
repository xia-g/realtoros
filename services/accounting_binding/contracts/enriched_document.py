"""
Accounting Binding — контракт EnrichedDocument.

Результат этапа Enrichment:
OCR-данные → бизнес-контекст.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from contracts.normalized_document import (
    DocumentType,
    EntityConfidence,
    NormalizedDocument,
)


class CounterpartyStatus(str, Enum):
    """Статус распознавания контрагента."""
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


class CounterpartyInfo(BaseModel):
    """Контрагент после обогащения."""
    status: CounterpartyStatus = CounterpartyStatus.UNKNOWN
    name: str = ""
    inn: str = ""
    kpp: str = ""
    canonical_id: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CanonicalEntity(BaseModel):
    """Каноническая сущность после нормализации."""
    raw_value: str
    normalized_value: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CanonicalAmount(BaseModel):
    """Нормализованная сумма."""
    raw_text: str
    amount: Decimal = Field(default=Decimal("0"), max_digits=16, decimal_places=2)
    currency: str = "RUB"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CanonicalDate(BaseModel):
    """Нормализованная дата."""
    raw_text: str
    parsed_date: date
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class EnrichedDocument(BaseModel):
    """Обогащённый документ с бизнес-контекстом.

    Результат enrichment: canonical entities, counterparty, parties, tags.
    """
    # Привязка к исходному OCR-документу
    schema_version: str = Field(default="1.0")
    document_id: str
    trace_id: str = ""
    source: str = ""
    document_type: DocumentType

    # Обогащённые сущности
    counterparty: CounterpartyInfo = Field(default_factory=CounterpartyInfo)
    counterparty_inn: str = ""
    counterparty_kpp: str = ""

    # Стороны сделки (Party Identity Resolution v1.5.1)
    parties: list[dict[str, Any]] = Field(default_factory=list)
    transaction_tags: list[str] = Field(default_factory=list)
    classification_hash: str = ""

    # Нормализованные поля
    canonical_amounts: list[CanonicalAmount] = Field(default_factory=list)
    canonical_dates: list[CanonicalDate] = Field(default_factory=list)
    document_number: str = ""
    vat_numbers: list[str] = Field(default_factory=list)
    ibans: list[str] = Field(default_factory=list)
    addresses: list[str] = Field(default_factory=list)
    persons: list[str] = Field(default_factory=list)

    # Метаданные обогащения
    enrichment_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    enrichment_warnings: list[str] = Field(default_factory=list)

    # Дедупликация
    dedup_hash: str = ""
    dedup_source_ids: list[str] = Field(default_factory=list)

    # Ссылка на исходный документ
    source_document: NormalizedDocument | None = None

    model_config = {"frozen": True, "extra": "forbid"}
