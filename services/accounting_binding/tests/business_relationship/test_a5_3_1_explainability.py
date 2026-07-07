"""
Tests — Knowledge Graph Explainability Model Phase A5.3.1.

All models: immutable, no logic, no build/calculate/explain.
NO Domain Services. NO algorithms.
"""
from __future__ import annotations

import pytest

from domain.business_relationship.ke_explanation_id import ExplanationId
from domain.business_relationship.ke_explanation_reason import ExplanationReasonType
from domain.business_relationship.ke_explanation_parts import ExplanationReason, ExplanationEvidence
from domain.business_relationship.ke_explanation_step import ExplanationStep
from domain.business_relationship.ke_explanation_metadata import ExplanationMetadata
from domain.business_relationship.ke_explanation import GraphExplanation
from domain.business_relationship.kg_identifiers import GraphNodeId


# ── ExplanationId Tests ──

class TestExplanationId:
    def test_generate(self):
        eid = ExplanationId.generate()
        assert bool(eid)

    def test_from_string(self):
        eid = ExplanationId.from_string("exp-1")
        assert eid.value == "exp-1"

    def test_from_string_empty_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            ExplanationId.from_string("")

    def test_immutable(self):
        eid = ExplanationId(value="x")
        with pytest.raises(Exception):
            eid.value = "y"

    def test_equality(self):
        assert ExplanationId(value="x") == ExplanationId(value="x")
        assert ExplanationId(value="x") != ExplanationId(value="y")

    def test_hashable(self):
        s = {ExplanationId(value="a"), ExplanationId(value="a")}
        assert len(s) == 1


# ── ExplanationReasonType Tests ──

class TestExplanationReasonType:
    def test_values(self):
        assert ExplanationReasonType.FACT_MATCH.value == "fact_match"
        assert ExplanationReasonType.TRUST.value == "trust"
        assert ExplanationReasonType.MANUAL.value == "manual"

    def test_all(self):
        for t in ExplanationReasonType:
            assert t.value


# ── ExplanationReason Tests ──

class TestExplanationReason:
    def test_create(self):
        r = ExplanationReason(
            reason_type=ExplanationReasonType.FACT_MATCH,
            summary="Matched fact INN",
            confidence=0.95,
        )
        assert r.reason_type == ExplanationReasonType.FACT_MATCH
        assert r.summary == "Matched fact INN"
        assert r.confidence == 0.95

    def test_immutable(self):
        r = ExplanationReason(ExplanationReasonType.DERIVED)
        with pytest.raises(Exception):
            r.summary = "changed"


# ── ExplanationEvidence Tests ──

class TestExplanationEvidence:
    def test_create(self):
        ev = ExplanationEvidence(
            source_type="document",
            source_id="doc-1",
            description="OCR extraction of INN",
            confidence=0.9,
        )
        assert ev.source_type == "document"
        assert ev.source_id == "doc-1"

    def test_immutable(self):
        ev = ExplanationEvidence()
        with pytest.raises(Exception):
            ev.source_id = "changed"


# ── ExplanationStep Tests ──

class TestExplanationStep:
    def test_create(self):
        reasons = (
            ExplanationReason(ExplanationReasonType.FACT_MATCH, "INN matched"),
        )
        step = ExplanationStep(step_number=1, summary="Found INN", reasons=reasons)
        assert step.step_number == 1
        assert len(step.reasons) == 1

    def test_empty(self):
        step = ExplanationStep()
        assert step.step_number == 0

    def test_immutable(self):
        step = ExplanationStep()
        with pytest.raises(Exception):
            step.summary = "changed"


# ── GraphExplanation Tests ──

class TestGraphExplanation:
    def test_create(self):
        eid = ExplanationId.generate()
        gid = GraphNodeId(value="n1")
        step = ExplanationStep(step_number=1, summary="Test step")
        exp = GraphExplanation(
            explanation_id=eid,
            graph_node_id=gid,
            steps=(step,),
            overall_confidence=0.85,
        )
        assert exp.explanation_id == eid
        assert exp.graph_node_id == gid
        assert exp.step_count == 1
        assert exp.overall_confidence == 0.85

    def test_empty(self):
        eid = ExplanationId.generate()
        gid = GraphNodeId(value="n1")
        exp = GraphExplanation(explanation_id=eid, graph_node_id=gid)
        assert exp.step_count == 0

    def test_immutable(self):
        eid = ExplanationId.generate()
        gid = GraphNodeId(value="n1")
        exp = GraphExplanation(explanation_id=eid, graph_node_id=gid)
        with pytest.raises(Exception):
            exp.steps = ()

    def test_equality(self):
        eid = ExplanationId(value="x")
        gid = GraphNodeId(value="n1")
        meta = ExplanationMetadata()
        e1 = GraphExplanation(explanation_id=eid, graph_node_id=gid, metadata=meta)
        e2 = GraphExplanation(explanation_id=eid, graph_node_id=gid, metadata=meta)
        assert e1 == e2

    def test_no_build_method(self):
        eid = ExplanationId.generate()
        gid = GraphNodeId(value="n1")
        exp = GraphExplanation(explanation_id=eid, graph_node_id=gid)
        assert not hasattr(exp, 'build')
        assert not hasattr(exp, 'calculate')
        assert not hasattr(exp, 'explain')
        assert not hasattr(exp, 'resolve')
        assert not hasattr(exp, 'append')
