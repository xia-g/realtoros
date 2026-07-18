"""
Document Role Resolution — business-semantic role of a document.

document_type (OCR): contract
document_role (semantic): sale_contract | transfer_act | egrn_extract | ...

OCR отвечает: "что написано"
Semantic Layer отвечает: "что это означает в бизнесе"
"""
from __future__ import annotations

from enum import Enum
from hashlib import sha256
from typing import Any


class DocumentRole(str, Enum):
    """Бизнес-роль документа в сделке."""
    SALE_CONTRACT = "sale_contract"
    TRANSFER_ACT = "transfer_act"
    EGRN_EXTRACT = "egrn_extract"
    PAYMENT_ORDER = "payment_order"
    PASSPORT = "passport"
    AMENDMENT = "amendment"
    INVOICE = "invoice"
    RECEIPT = "receipt"
    OTHER_CONTRACT = "other_contract"
    CADASTRAL = "cadastral"
    CERTIFICATE = "certificate"
    RECONCILIATION = "reconciliation"
    ADVANCE_REPORT = "advance_report"
    UNKNOWN = "unknown"


class ClassificationSource(str, Enum):
    """Источник классификации роли."""
    OCR = "OCR"
    SEMANTIC = "SEMANTIC"
    USER = "USER"


class DocumentSemantic:
    """Семантическая модель документа: тип + роль + уверенность.

    Пример:
      DocumentSemantic(
          document_type="contract",
          document_role=DocumentRole.TRANSFER_ACT,
          confidence=0.97,
          source=ClassificationSource.SEMANTIC,
      )
    """

    def __init__(
        self,
        document_type: str = "",
        document_role: DocumentRole = DocumentRole.UNKNOWN,
        confidence: float = 0.0,
        source: ClassificationSource = ClassificationSource.OCR,
    ):
        self.document_type = document_type
        self.document_role = document_role
        self.confidence = round(confidence, 4)
        self.source = source

    @property
    def semantic_hash(self) -> str:
        """Детерминированный хеш семантики."""
        raw = f"{self.document_type}|{self.document_role.value}|{self.confidence}|{self.source.value}"
        return sha256(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_type": self.document_type,
            "document_role": self.document_role.value,
            "confidence": self.confidence,
            "source": self.source.value,
            "semantic_hash": self.semantic_hash,
        }

    def __eq__(self, other):
        if not isinstance(other, DocumentSemantic):
            return False
        return self.semantic_hash == other.semantic_hash

    def __repr__(self):
        return f"DocSem({self.document_type}→{self.document_role.value} @ {self.confidence})"
