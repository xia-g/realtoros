"""
DocumentFingerprint + TransactionFingerprint — immutable snapshots.

DocumentFingerprint: извлекается из OCR результата (NormalizedDocument).
TransactionFingerprint: бизнес-отпечаток сделки — то с чем работает DealResolver.

Оба immutable (frozen dataclass).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from typing import Any

from domain.property.property_identity import PropertyIdentity


class TransactionDirection(str, Enum):
    PURCHASE = "purchase"       # Мы покупаем
    SALE = "sale"               # Мы продаём
    LEASE = "lease"             # Аренда
    MORTGAGE = "mortgage"       # Ипотека
    RENOVATION = "renovation"   # Ремонт
    AGENCY = "agency"           # Агентский договор
    OTHER = "other"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True)
class MatchingEvidence:
    """Доказательство совпадения или расхождения поля."""
    field: str
    document_value: str
    candidate_value: str
    weight: float
    matched: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "document_value": self.document_value,
            "candidate_value": self.candidate_value,
            "weight": self.weight,
            "matched": self.matched,
        }


@dataclass(frozen=True)
class SimilarityResult:
    """Результат сравнения двух fingerprint'ов."""
    score: float
    confidence: ConfidenceLevel
    evidence: list[MatchingEvidence] = field(default_factory=list)

    @property
    def reasons(self) -> list[dict]:
        return [e.to_dict() for e in self.evidence]


@dataclass(frozen=True)
class DocumentFingerprint:
    """Отпечаток документа: что извлёк OCR + Semantic Intelligence.

    Вход для DealResolver.
    """
    fingerprint_version: int = 1
    document_id: str = ""
    document_type: str = ""
    document_role: str = ""
    raw_text: str = ""
    entities: dict[str, list[str]] = field(default_factory=dict)

    # Extracted fields
    amount: Decimal = Decimal("0")
    contract_date: date | None = None
    contract_number: str = ""
    buyer: str = ""
    seller: str = ""
    parties: list[dict] = field(default_factory=list)
    counterparty_inn: str = ""

    # Property
    property_identity: PropertyIdentity | None = None

    @property
    def fingerprint_hash(self) -> str:
        """Детерминированный хеш fingerprint'а (без document_id)."""
        raw = (
            f"{self.document_type}|{self.document_role}|{self.amount}|"
            f"{self.buyer}|{self.seller}|{self.contract_number}|"
            f"{self.contract_date}|"
            f"{self.property_identity.identity_hash if self.property_identity else ''}"
        )
        return sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class TransactionFingerprint:
    """Бизнес-отпечаток транзакции.

    DealResolver работает только с TransactionFingerprint.
    Содержит всё необходимое для поиска кандидатов и скоринга.
    """
    fingerprint_version: int = 1

    # Transaction
    transaction_type: str = ""
    transaction_direction: str = ""

    # Document
    document_role: str = ""
    contract_number: str = ""
    contract_date: date | None = None

    # Amount
    amount: Decimal = Decimal("0")

    # Parties
    buyer: str = ""
    seller: str = ""
    buyer_inn: str = ""
    seller_inn: str = ""
    our_side: str = ""
    party_count: int = 0

    # Property
    property_identity: PropertyIdentity | None = None

    @property
    def transaction_hash(self) -> str:
        """Хеш транзакции для дедупликации."""
        raw = (
            f"{self.transaction_type}|{self.transaction_direction}|"
            f"{self.contract_number}|{self.buyer_inn}|{self.seller_inn}|"
            f"{self.property_identity.identity_hash if self.property_identity else ''}"
        )
        return sha256(raw.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def from_document_fingerprint(cls, doc_fp: DocumentFingerprint) -> TransactionFingerprint:
        """Создать TransactionFingerprint из DocumentFingerprint."""
        # Определить direction по parties
        direction = TransactionDirection.PURCHASE.value
        our_party = ""
        for p in doc_fp.parties:
            if p.get("relation", {}).get("role") == "our_side":
                our_party = p.get("identity", {}).get("name", "")
        if our_party and our_party.lower() in (doc_fp.seller.lower() if doc_fp.seller else ""):
                direction = TransactionDirection.SALE.value

        buyer_inn = ""
        seller_inn = ""
        for p in doc_fp.parties:
            rel = p.get("relation", {})
            identity = p.get("identity", {})
            if rel.get("role") == "counterparty" and rel.get("relation") == "external":
                # Противоположная сторона
                if doc_fp.buyer and identity.get("name", "").lower() in doc_fp.buyer.lower():
                    seller_inn = identity.get("inn", "") or doc_fp.counterparty_inn
                else:
                    buyer_inn = identity.get("inn", "") or doc_fp.counterparty_inn

        return cls(
            fingerprint_version=doc_fp.fingerprint_version,
            transaction_type=doc_fp.document_role,
            transaction_direction=direction,
            document_role=doc_fp.document_role,
            contract_number=doc_fp.contract_number,
            contract_date=doc_fp.contract_date,
            amount=doc_fp.amount,
            buyer=doc_fp.buyer,
            seller=doc_fp.seller,
            buyer_inn=buyer_inn,
            seller_inn=seller_inn,
            our_side=our_party,
            party_count=len(doc_fp.parties),
            property_identity=doc_fp.property_identity,
        )
