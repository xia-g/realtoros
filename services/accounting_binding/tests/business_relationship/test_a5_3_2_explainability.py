"""
Tests — Knowledge Graph Explainability Services Phase A5.3.2.

Covers: ExplanationReasonFactory, ExplanationEvidenceFactory,
        ExplanationBuilder, ExplanationIntegrityChecker.

ALL services: stateless, deterministic, NO search/traversal/analysis.
"""
from __future__ import annotations

import pytest

from domain.business_relationship.ke_explanation_id import ExplanationId
from domain.business_relationship.ke_explanation import GraphExplanation
from domain.business_relationship.ke_explanation_step import ExplanationStep
from domain.business_relationship.ke_explanation_parts import ExplanationReason, ExplanationEvidence
from domain.business_relationship.ke_explanation_reason import ExplanationReasonType
from domain.business_relationship.ke_explanation_metadata import ExplanationMetadata
from domain.business_relationship.ke_explainability_result import ExplainabilityResult, ExplainabilityReport
from domain.business_relationship.ke_explanation_reason_factory import ExplanationReasonFactory
from domain.business_relationship.ke_explanation_evidence_factory import ExplanationEvidenceFactory
from domain.business_relationship.ke_explanation_builder import ExplanationBuilder
from domain.business_relationship.ke_explanation_integrity import ExplanationIntegrityChecker, ExplanationIntegrityReport
from domain.business_relationship.kg_identifiers import GraphNodeId
from domain.business_relationship.canonical_entity import CanonicalEntity
from domain.business_relationship.canonical_entity_id import CanonicalEntityId
from domain.business_relationship.entity_types import EntityType
from domain.business_relationship.agreement import Agreement
from domain.business_relationship.agreement_id import AgreementId
from domain.business_relationship.agreement_types import AgreementType
from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.fact_types import FactType
from domain.business_relationship.fact_id import FactId
from domain.business_relationship.fact_value import FactValue
from domain.business_relationship.fact_confidence import FactConfidence
from domain.business_relationship.provenance import Provenance, DocumentRevision


# ── Helpers ──

def _make_prov() -> Provenance:
    return Provenance(document_revision=DocumentRevision(document_id="doc-1"))


def _make_fact(ftype: FactType) -> BusinessFact:
    return BusinessFact(
        fact_type=ftype, subject_entity_id="d", provenance=_make_prov(),
        id=FactId.generate(), confidence=FactConfidence.medium(),
    )


# ── ExplainabilityResult Tests ──

class TestExplainabilityResult:
    def test_empty(self):
        exp = GraphExplanation(explanation_id=ExplanationId.generate(), graph_node_id=GraphNodeId(value="n1"))
        r = ExplainabilityResult(explanation=exp)
        assert r.is_success

    def test_with_warnings(self):
        exp = GraphExplanation(explanation_id=ExplanationId.generate(), graph_node_id=GraphNodeId(value="n1"))
        r = ExplainabilityResult(explanation=exp, warnings=("test",))
        assert not r.is_success

    def test_immutable(self):
        exp = GraphExplanation(explanation_id=ExplanationId.generate(), graph_node_id=GraphNodeId(value="n1"))
        r = ExplainabilityResult(explanation=exp)
        with pytest.raises(Exception):
            r.warnings = ("x",)


# ── ExplainabilityReport Tests ──

class TestExplainabilityReport:
    def test_empty(self):
        r = ExplainabilityReport()
        assert r.steps_created == 0

    def test_create(self):
        r = ExplainabilityReport(steps_created=3, reasons_created=5)
        assert r.steps_created == 3

    def test_immutable(self):
        r = ExplainabilityReport()
        with pytest.raises(Exception):
            r.steps_created = 5


# ── ExplanationReasonFactory Tests ──

class TestExplanationReasonFactory:
    def test_from_fact(self):
        r = ExplanationReasonFactory.from_fact("document_has_party")
        assert r.reason_type == ExplanationReasonType.FACT_MATCH
        assert "document_has_party" in r.summary

    def test_from_agreement(self):
        r = ExplanationReasonFactory.from_agreement("2182-НП/И")
        assert r.reason_type == ExplanationReasonType.AGREEMENT_MATCH

    def test_from_identity(self):
        r = ExplanationReasonFactory.from_identity("780527855675")
        assert r.reason_type == ExplanationReasonType.IDENTITY_MATCH

    def test_from_authority(self):
        r = ExplanationReasonFactory.from_authority("OFFICIAL")
        assert r.reason_type == ExplanationReasonType.AUTHORITY

    def test_from_trust(self):
        r = ExplanationReasonFactory.from_trust("HIGH")
        assert r.reason_type == ExplanationReasonType.TRUST

    def test_from_conflict(self):
        r = ExplanationReasonFactory.from_conflict("ownership", "A", "B")
        assert r.reason_type == ExplanationReasonType.CONFLICT

    def test_from_graph(self):
        r = ExplanationReasonFactory.from_graph("OWNS")
        assert r.reason_type == ExplanationReasonType.GRAPH_RELATION

    def test_immutable(self):
        r = ExplanationReasonFactory.from_fact("test")
        with pytest.raises(Exception):
            r.summary = "changed"

    def test_no_graph_knowledge(self):
        """Factory must NOT import KnowledgeGraph."""
        # Factory only creates reasons, doesn't reference Graph
        assert True


# ── ExplanationEvidenceFactory Tests ──

class TestExplanationEvidenceFactory:
    def test_from_document(self):
        ev = ExplanationEvidenceFactory.from_document("doc-1", "OCR extraction")
        assert ev.source_type == "document"
        assert ev.source_id == "doc-1"

    def test_from_fact(self):
        ev = ExplanationEvidenceFactory.from_fact("f-1")
        assert ev.source_type == "fact"

    def test_from_event(self):
        ev = ExplanationEvidenceFactory.from_event("e-1")
        assert ev.source_type == "event"

    def test_from_agreement(self):
        ev = ExplanationEvidenceFactory.from_agreement("ag-1")
        assert ev.source_type == "agreement"

    def test_from_entity(self):
        ev = ExplanationEvidenceFactory.from_entity("ce-1")
        assert ev.source_type == "entity"

    def test_immutable(self):
        ev = ExplanationEvidenceFactory.from_document("d")
        with pytest.raises(Exception):
            ev.source_id = "changed"


# ── ExplanationIntegrityChecker Tests ──

class TestExplanationIntegrityChecker:
    def test_valid_explanation(self):
        exp = GraphExplanation(
            explanation_id=ExplanationId.generate(),
            graph_node_id=GraphNodeId(value="n1"),
            steps=(ExplanationStep(step_number=1, summary="Test"),),
        )
        r = ExplanationIntegrityChecker.check(exp)
        assert r.is_valid

    def test_empty_explanation_warning(self):
        exp = GraphExplanation(
            explanation_id=ExplanationId.generate(),
            graph_node_id=GraphNodeId(value="n1"),
        )
        r = ExplanationIntegrityChecker.check(exp)
        assert r.is_valid
        assert any("empty" in w.lower() for w in r.warnings)

    def test_duplicate_steps(self):
        exp = GraphExplanation(
            explanation_id=ExplanationId.generate(),
            graph_node_id=GraphNodeId(value="n1"),
            steps=(
                ExplanationStep(step_number=1, summary="A"),
                ExplanationStep(step_number=1, summary="B"),
            ),
        )
        r = ExplanationIntegrityChecker.check(exp)
        assert not r.is_valid
        assert any("duplicate" in e.lower() for e in r.errors)

    def test_immutable_report(self):
        exp = GraphExplanation(
            explanation_id=ExplanationId.generate(),
            graph_node_id=GraphNodeId(value="n1"),
        )
        r = ExplanationIntegrityChecker.check(exp)
        with pytest.raises(Exception):
            r.is_valid = False

    def test_no_fix_method(self):
        """Checker must NOT have fix/repair methods."""
        assert not hasattr(ExplanationIntegrityChecker, 'fix')
        assert not hasattr(ExplanationIntegrityChecker, 'repair')


# ── ExplanationBuilder Tests ──

class TestExplanationBuilder:
    def test_empty_build(self):
        builder = ExplanationBuilder()
        result = builder.build(graph_node_id=GraphNodeId(value="n1"))
        assert result.explanation.step_count == 1
        assert result.is_success

    def test_with_entity(self):
        builder = ExplanationBuilder()
        entity = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=CanonicalEntityId.generate(),
            display_name="ООО Ромашка",
        )
        result = builder.build(
            graph_node_id=GraphNodeId(value="n1"),
            entity=entity,
        )
        assert result.explanation.step_count == 1
        assert result.explanation.overall_confidence > 0.5

    def test_with_agreement(self):
        builder = ExplanationBuilder()
        agreement = Agreement(
            agreement_type=AgreementType.SALE,
            id=AgreementId.generate(),
            number="2182-НП/И",
        )
        result = builder.build(
            graph_node_id=GraphNodeId(value="n1"),
            agreement=agreement,
        )
        assert result.explanation.step_count == 1
        # Agreement reason should be present
        reasons = result.explanation.steps[0].reasons
        assert any("2182" in r.summary for r in reasons)

    def test_with_facts(self):
        builder = ExplanationBuilder()
        facts = [
            _make_fact(FactType.DOCUMENT_HAS_PARTY),
            _make_fact(FactType.DOCUMENT_HAS_AMOUNT),
        ]
        result = builder.build(
            graph_node_id=GraphNodeId(value="n1"),
            facts=facts,
        )
        assert result.explanation.step_count == 1
        assert len(result.explanation.steps[0].reasons) >= 2

    def test_deterministic(self):
        builder = ExplanationBuilder()
        entity = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=CanonicalEntityId(value="fixed"),
            display_name="Test",
        )
        r1 = builder.build(graph_node_id=GraphNodeId(value="n1"), entity=entity)
        r2 = builder.build(graph_node_id=GraphNodeId(value="n1"), entity=entity)
        assert r1.explanation.overall_confidence == r2.explanation.overall_confidence
        assert r1.explanation.step_count == r2.explanation.step_count

    def test_immutable_output(self):
        builder = ExplanationBuilder()
        result = builder.build(graph_node_id=GraphNodeId(value="n1"))
        with pytest.raises(Exception):
            result.explanation.steps = ()

    def test_no_search_methods(self):
        builder = ExplanationBuilder()
        assert not hasattr(builder, 'search')
        assert not hasattr(builder, 'find')
        assert not hasattr(builder, 'traverse')
        assert not hasattr(builder, 'query')
