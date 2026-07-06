"""
BusinessFact — immutable observation extracted from a document.

@dataclass(frozen=True) — NO mutation after creation.
Facts DO NOT interpret. Inference is a separate layer.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from domain.business_relationship.fact_types import FactType
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
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    object_entity_id: str | None = None
    value: str | None = None          # для AMOUNT_OF (сумма), DATE_OF (дата)
    confidence: float = 1.0

    @property
    def document_id(self) -> str:
        return self.provenance.document_revision.document_id

    @property
    def document_revision(self) -> DocumentRevision:
        return self.provenance.document_revision

    def __repr__(self) -> str:
        parts = [f"{self.fact_type.value}(subject={self.subject_entity_id[:8]})"]
        if self.object_entity_id:
            parts.append(f"object={self.object_entity_id[:8]})")
        if self.value:
            parts.append(f"value={self.value})")
        return " ".join(parts)
