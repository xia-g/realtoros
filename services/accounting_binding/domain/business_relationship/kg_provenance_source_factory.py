"""
ProvenanceSourceFactory — creates ProvenanceSource instances.

Stateless. NO graph knowledge. NO analysis.
"""
from __future__ import annotations

from domain.business_relationship.kg_provenance_source import ProvenanceSource, ProvenanceSourceType


class ProvenanceSourceFactory:
    """Создаёт источники происхождения. Не знает о Graph или KnowledgeProvenance."""

    @staticmethod
    def from_document(document_id: str, description: str = "") -> ProvenanceSource:
        return ProvenanceSource(
            source_type=ProvenanceSourceType.DOCUMENT,
            source_id=document_id,
            description=description,
        )

    @staticmethod
    def from_fact(fact_id: str, description: str = "") -> ProvenanceSource:
        return ProvenanceSource(
            source_type=ProvenanceSourceType.FACT,
            source_id=fact_id,
            description=description,
        )

    @staticmethod
    def from_agreement(agreement_id: str, description: str = "") -> ProvenanceSource:
        return ProvenanceSource(
            source_type=ProvenanceSourceType.AGREEMENT,
            source_id=agreement_id,
            description=description,
        )

    @staticmethod
    def from_entity(entity_id: str, description: str = "") -> ProvenanceSource:
        return ProvenanceSource(
            source_type=ProvenanceSourceType.ENTITY,
            source_id=entity_id,
            description=description,
        )

    @staticmethod
    def from_event(event_id: str, description: str = "") -> ProvenanceSource:
        return ProvenanceSource(
            source_type=ProvenanceSourceType.KNOWLEDGE_EVENT,
            source_id=event_id,
            description=description,
        )
