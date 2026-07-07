"""
ExplanationReasonFactory — creates ExplanationReason instances.

Stateless. NO graph knowledge. NO analysis.
"""
from __future__ import annotations

from domain.business_relationship.ke_explanation_reason import ExplanationReasonType
from domain.business_relationship.ke_explanation_parts import ExplanationReason


class ExplanationReasonFactory:
    """Создаёт причины объяснения. Не знает о Graph или Explanation."""

    @staticmethod
    def from_fact(fact_type: str, domain_id: str = "", confidence: float = 0.9) -> ExplanationReason:
        return ExplanationReason(
            reason_type=ExplanationReasonType.FACT_MATCH,
            summary=f"Fact: {fact_type}",
            confidence=confidence,
            related_domain_id=domain_id,
        )

    @staticmethod
    def from_agreement(agreement_number: str, domain_id: str = "") -> ExplanationReason:
        return ExplanationReason(
            reason_type=ExplanationReasonType.AGREEMENT_MATCH,
            summary=f"Agreement: {agreement_number}",
            confidence=0.95,
            related_domain_id=domain_id,
        )

    @staticmethod
    def from_identity(identifier: str, domain_id: str = "") -> ExplanationReason:
        return ExplanationReason(
            reason_type=ExplanationReasonType.IDENTITY_MATCH,
            summary=f"Identity: {identifier}",
            confidence=0.95,
            related_domain_id=domain_id,
        )

    @staticmethod
    def from_authority(authority_level: str) -> ExplanationReason:
        return ExplanationReason(
            reason_type=ExplanationReasonType.AUTHORITY,
            summary=f"Authority: {authority_level}",
            confidence=0.9,
        )

    @staticmethod
    def from_trust(trust_level: str) -> ExplanationReason:
        return ExplanationReason(
            reason_type=ExplanationReasonType.TRUST,
            summary=f"Trust: {trust_level}",
            confidence=0.85,
        )

    @staticmethod
    def from_conflict(field: str, value_a: str, value_b: str) -> ExplanationReason:
        return ExplanationReason(
            reason_type=ExplanationReasonType.CONFLICT,
            summary=f"Conflict in {field}: {value_a} vs {value_b}",
            confidence=0.7,
        )

    @staticmethod
    def from_graph(relation: str) -> ExplanationReason:
        return ExplanationReason(
            reason_type=ExplanationReasonType.GRAPH_RELATION,
            summary=f"Graph relation: {relation}",
            confidence=0.9,
        )
