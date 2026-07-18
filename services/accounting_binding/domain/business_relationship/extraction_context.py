"""
ExtractionContext — временная модель для v2.0.1.

Содержит результат извлечения сущностей и фактов.
Используется внутри пайплайна, NOT persistent.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

from domain.business_relationship.entity import BusinessEntity, EntityIdentifier
from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.document_reference import DocumentReference


@dataclass
class ExtractionContext:
    """Результат извлечения. In-memory only."""
    document_id: str = ""
    entities: list[BusinessEntity] = field(default_factory=list)
    identifiers: list[EntityIdentifier] = field(default_factory=list)
    facts: list[BusinessFact] = field(default_factory=list)
    document_references: list[DocumentReference] = field(default_factory=list)

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    @property
    def fact_count(self) -> int:
        return len(self.facts)

    @property
    def summary(self) -> str:
        """Краткое текстовое описание."""
        entity_types = {}
        for e in self.entities:
            t = e.entity_type.value
            entity_types[t] = entity_types.get(t, 0) + 1
        fact_types = {}
        for f in self.facts:
            t = f.fact_type.value
            fact_types[t] = fact_types.get(t, 0) + 1
        return (
            f"ExtractionContext(document={self.document_id[:12]}..., "
            f"entities={entity_types}, "
            f"facts={fact_types})"
        )
