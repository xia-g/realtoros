"""
Trust Model — enterprise-level trust in knowledge.

Confidence = quality of OCR extraction (extrinsic).
Trust = how much the corporate knowledge base trusts the fact (intrinsic).

Trust never decreases automatically. Decrease only by explicit event.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TrustLevel(str, Enum):
    UNKNOWN = "unknown"     # no evidence
    LOW = "low"             # one weak source
    MEDIUM = "medium"       # two or more moderate sources
    HIGH = "high"           # multiple strong sources, no conflicts
    VERIFIED = "verified"   # confirmed by official source (EGRN, notary)


# Mapping: number of strong confirmations → trust level
TRUST_THRESHOLDS = [
    (0, TrustLevel.UNKNOWN),
    (1, TrustLevel.LOW),
    (2, TrustLevel.MEDIUM),
    (4, TrustLevel.HIGH),
    (float("inf"), TrustLevel.VERIFIED),
]


@dataclass
class TrustScore:
    """Текущая оценка доверия к знанию."""
    entity_id: str
    current_level: TrustLevel = TrustLevel.UNKNOWN
    supporting_documents: list[str] = field(default_factory=list)
    supporting_agreements: list[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    history: list[dict] = field(default_factory=list)  # [{level, reason, doc_id, timestamp}]

    def add_evidence(self, document_id: str, agreement_id: str = "", 
                     is_official: bool = False):
        """Добавить свидетельство. Trust только растёт."""
        if document_id not in self.supporting_documents:
            self.supporting_documents.append(document_id)
        if agreement_id and agreement_id not in self.supporting_agreements:
            self.supporting_agreements.append(agreement_id)

        old_level = self.current_level
        new_level = self._compute_level(extra_official=is_official)

        if new_level != old_level:
            self.history.append({
                "old_level": old_level.value,
                "new_level": new_level.value,
                "document_id": document_id,
                "agreement_id": agreement_id,
                "timestamp": datetime.utcnow().isoformat(),
            })
            self.current_level = new_level
            self.last_updated = datetime.utcnow()

    def _compute_level(self, extra_official: bool = False) -> TrustLevel:
        effective = len(self.supporting_documents) + (1 if extra_official else 0)
        if effective >= 6:
            return TrustLevel.VERIFIED
        elif effective >= 4:
            return TrustLevel.HIGH
        elif effective >= 2:
            return TrustLevel.MEDIUM
        elif effective >= 1:
            return TrustLevel.LOW
        return TrustLevel.UNKNOWN

    @property
    def score(self) -> float:
        """Numeric 0.0-1.0."""
        mapping = {
            TrustLevel.UNKNOWN: 0.0,
            TrustLevel.LOW: 0.25,
            TrustLevel.MEDIUM: 0.5,
            TrustLevel.HIGH: 0.75,
            TrustLevel.VERIFIED: 1.0,
        }
        return mapping.get(self.current_level, 0.0)
