"""
ExplanationEvidenceFactory — creates ExplanationEvidence instances.

Stateless. NO analysis. NO search.
"""
from __future__ import annotations

from domain.business_relationship.ke_explanation_parts import ExplanationEvidence


class ExplanationEvidenceFactory:
    """Создаёт доказательства объяснения. Не анализирует данные."""

    @staticmethod
    def from_document(document_id: str, description: str = "") -> ExplanationEvidence:
        return ExplanationEvidence(
            source_type="document",
            source_id=document_id,
            description=description,
            confidence=0.95,
        )

    @staticmethod
    def from_fact(fact_id: str, description: str = "") -> ExplanationEvidence:
        return ExplanationEvidence(
            source_type="fact",
            source_id=fact_id,
            description=description,
            confidence=0.9,
        )

    @staticmethod
    def from_event(event_id: str, description: str = "") -> ExplanationEvidence:
        return ExplanationEvidence(
            source_type="event",
            source_id=event_id,
            description=description,
            confidence=0.85,
        )

    @staticmethod
    def from_agreement(agreement_id: str, description: str = "") -> ExplanationEvidence:
        return ExplanationEvidence(
            source_type="agreement",
            source_id=agreement_id,
            description=description,
            confidence=0.95,
        )

    @staticmethod
    def from_entity(entity_id: str, description: str = "") -> ExplanationEvidence:
        return ExplanationEvidence(
            source_type="entity",
            source_id=entity_id,
            description=description,
            confidence=0.9,
        )
