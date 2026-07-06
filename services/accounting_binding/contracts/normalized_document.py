"""
Accounting Binding — входной контракт из OCR.

IMMUTABLE — НЕ ИЗМЕНЯТЬ.
Источник: RealtorOS OCR Node v1.1.0 (normalized_document).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Типы документов, поддерживаемые OCR-контуром."""
    INVOICE = "invoice"
    CONTRACT = "contract"
    ACT = "act"
    BANK_STATEMENT = "bank_statement"
    REGISTRY_EXTRACT = "registry_extract"
    RECEIPT = "receipt"
    UNKNOWN = "unknown"


class EntityConfidence(BaseModel):
    """Детальная уверенность по компонентам распознавания."""
    ocr_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    classification_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    entities_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    overall_confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class NormalizedEntities(BaseModel):
    """Сущности, извлечённые OCR-контуром."""
    date: list[str] = Field(default_factory=list)
    document_number: list[str] = Field(default_factory=list)
    company: list[str] = Field(default_factory=list)
    vat_number: list[str] = Field(default_factory=list)
    currency: list[str] = Field(default_factory=list)
    amount: list[float] = Field(default_factory=list)
    iban: list[str] = Field(default_factory=list)
    addresses: list[str] = Field(default_factory=list)
    persons: list[str] = Field(default_factory=list)


class NormalizedDocument(BaseModel):
    """Входной контракт из OCR-контура.
    
    SCHEMA_VERSION = "1.0"
    immutable, JSON, UTF-8, snake_case, exclude_none.
    """
    schema_version: str = Field(default="1.0", alias="schema_version")
    document_id: str
    trace_id: str = ""
    source: str = ""
    document_type: DocumentType
    pages: int = Field(default=0, ge=0)
    entities: NormalizedEntities = Field(default_factory=NormalizedEntities)
    tables: list[list[dict[str, Any]]] = Field(default_factory=list)
    raw_text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    confidence: EntityConfidence = Field(default_factory=EntityConfidence)
    warnings: list[str] = Field(default_factory=list)

    model_config = {"frozen": True, "extra": "forbid"}
