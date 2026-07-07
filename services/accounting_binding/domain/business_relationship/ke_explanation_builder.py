"""
ExplanationBuilder — coordinator of explanation construction.

Stateless. Deterministic. Creates new GraphExplanation each call.
NO search. NO traversal. NO analysis.
"""
from __future__ import annotations

from domain.business_relationship.ke_explanation_id import ExplanationId
from domain.business_relationship.ke_explanation import GraphExplanation
from domain.business_relationship.ke_explanation_step import ExplanationStep
from domain.business_relationship.ke_explanation_parts import ExplanationReason, ExplanationEvidence
from domain.business_relationship.ke_explainability_result import ExplainabilityResult, ExplainabilityReport
from domain.business_relationship.ke_explanation_reason_factory import ExplanationReasonFactory
from domain.business_relationship.ke_explanation_evidence_factory import ExplanationEvidenceFactory
from domain.business_relationship.ke_explanation_integrity import ExplanationIntegrityChecker, ExplanationIntegrityReport
from domain.business_relationship.kg_identifiers import GraphNodeId
from domain.business_relationship.kg_graph import KnowledgeGraph
from domain.business_relationship.canonical_entity import CanonicalEntity
from domain.business_relationship.agreement import Agreement
from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.fact_types import FactType


class ExplanationBuilder:
    """Строит новое GraphExplanation из доменных объектов.

    Stateless. Deterministic. NO search. NO traversal.
    """

    def __init__(self):
        self._reason_factory = ExplanationReasonFactory()
        self._evidence_factory = ExplanationEvidenceFactory()
        self._integrity_checker = ExplanationIntegrityChecker()

    def build(
        self,
        graph_node_id: GraphNodeId,
        entity: CanonicalEntity | None = None,
        agreement: Agreement | None = None,
        facts: list[BusinessFact] | None = None,
    ) -> ExplainabilityResult:
        """Build GraphExplanation from domain objects."""
        reasons: list[ExplanationReason] = []
        evidence: list[ExplanationEvidence] = []

        # 1. Entity identity reason
        if entity:
            reasons.append(self._reason_factory.from_identity(
                identifier=entity.display_name or str(entity.id),
                domain_id=str(entity.id),
            ))
            evidence.append(self._evidence_factory.from_entity(
                entity_id=str(entity.id),
                description=f"Entity {entity.display_name}",
            ))

        # 2. Agreement reasons
        if agreement:
            reasons.append(self._reason_factory.from_agreement(
                agreement_number=agreement.number or str(agreement.id),
                domain_id=str(agreement.id),
            ))
            evidence.append(self._evidence_factory.from_agreement(
                agreement_id=str(agreement.id),
                description=f"Agreement {agreement.number}",
            ))

        # 3. Fact reasons
        for fact in (facts or []):
            reasons.append(self._reason_factory.from_fact(
                fact_type=fact.fact_type.value,
                domain_id=str(fact.id),
            ))
            evidence.append(self._evidence_factory.from_fact(
                fact_id=str(fact.id),
                description=f"Fact {fact.fact_type.value}",
            ))

        # 4. Build steps
        steps: list[ExplanationStep] = []
        if reasons:
            steps.append(ExplanationStep(
                step_number=1,
                summary=f"Explanation for node {graph_node_id}",
                reasons=tuple(reasons),
                evidence=tuple(evidence),
            ))
        else:
            steps.append(ExplanationStep(
                step_number=1,
                summary=f"No reasons available for node {graph_node_id}",
            ))

        # 5. Build explanation
        confidence = 0.95 if reasons else 0.3
        explanation = GraphExplanation(
            explanation_id=ExplanationId.generate(),
            graph_node_id=graph_node_id,
            steps=tuple(steps),
            overall_confidence=confidence,
        )

        # 6. Integrity check
        report = self._integrity_checker.check(explanation)

        return ExplainabilityResult(
            explanation=explanation,
            warnings=tuple(report.warnings) + tuple(report.errors) if not report.is_valid else (),
        )
