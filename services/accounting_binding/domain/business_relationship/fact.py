"""
BusinessFact — immutable observation extracted from a document.

@dataclass(frozen=True) — NO mutation after creation.
Facts DO NOT interpret. Inference is a separate layer.

Uses typed value objects: FactId, FactValue, FactConfidence, FactSource, FactEvidence.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.business_relationship.fact_types import FactType
from domain.business_relationship.fact_id import FactId
from domain.business_relationship.fact_value import FactValue
from domain.business_relationship.fact_confidence import FactConfidence
from domain.business_relationship.fact_source import FactSource
from domain.business_relationship.fact_evidence import FactEvidence
from domain.business_relationship.provenance import Provenance, DocumentRevision


@dataclass(frozen=True)
class BusinessFact:
    """Факт — сырое наблюдение из документа.

    Immutable. Не содержит выводов.
    Привязан к конкретной ревизии документа.
    """
    fact_type: FactType
    subject_entity_id: str
    provenance: Provenance
    id: FactId
    object_entity_id: str | None = None
    value: FactValue | None = None
    confidence: FactConfidence | None = None

    @property
    def document_id(self) -> str:
        return self.provenance.document_revision.document_id

    @property
    def document_revision(self) -> DocumentRevision:
        return self.provenance.document_revision

    def __repr__(self) -> str:
        parts = [f"{self.fact_type.value}(subject={self.subject_entity_id[:8]})"]
        if self.object_entity_id:
            parts.append(f"object={self.object_entity_id[:8]}")
        if self.value:
            parts.append(f"value={self.value}")
        if self.confidence:
            parts.append(f"conf={float(self.confidence):.2f}")
        return " ".join(parts)
