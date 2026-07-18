"""
Tests — Knowledge Graph v2.0.5c — Domain Integrity & Explainability
"""
from __future__ import annotations

import pytest

from domain.business_relationship.knowledge_graph import (
    KnowledgeGraph, GraphNode, GraphEdge, GraphNodeType, EdgeType,
    NodeProvenance, EdgeProvenance, PathExplanation, GraphValidationReport,
    TraversalOptions, GraphBuilder, WorkspaceGraph, ContextQuery,
    stable_id,
)
from domain.business_relationship.entity import BusinessEntity
from domain.business_relationship.entity_types import EntityType as ET


# ── Stable ID Tests ──

class TestStableIDs:
    def test_deterministic(self):
        assert stable_id("ENTITY", "abc") == "ENTITY:abc"
        assert stable_id("PROPERTY", "78:10:1") == "PROPERTY:78:10:1"

    def test_no_double_prefix(self):
        assert stable_id("ENTITY", "ENTITY:abc") == "ENTITY:abc"

    def test_no_random_uuids(self):
        nid = stable_id("DOCUMENT", "doc-42")
        assert "uuid" not in nid.lower()


# ── Provenance Tests ──

class TestProvenance:
    def test_node_provenance_immutable(self):
        p = NodeProvenance("entity", "e-1", document_ids=["doc-1"])
        with pytest.raises(Exception):
            p.source_id = "e-2"

    def test_edge_provenance(self):
        p = EdgeProvenance(supporting_fact_ids=["f-1"], supporting_document_ids=["d-1"])
        assert len(p.supporting_fact_ids) == 1

    def test_node_with_provenance(self):
        p = NodeProvenance("entity", "e-1", 1, ["doc-1"])
        n = GraphNode("ENTITY:e-1", GraphNodeType.ENTITY, "e-1", "Test", provenance=p)
        assert n.provenance is not None
        assert n.provenance.source_type == "entity"

    def test_edge_with_provenance(self):
        p = EdgeProvenance(supporting_fact_ids=["f-1"], supporting_document_ids=["d-1"])
        e = GraphEdge("a", "b", EdgeType.MENTIONS, provenance=p)
        assert e.provenance is not None


# ── Graph Validation Report Tests ──

class TestGraphValidation:
    def test_valid_graph(self):
        g = KnowledgeGraph()
        g._add_node(GraphNode("ENTITY:a", GraphNodeType.ENTITY, "a", "A"))
        g._add_node(GraphNode("DOCUMENT:d", GraphNodeType.DOCUMENT, "d", "D"))
        g._add_edge(GraphEdge("d", "a", EdgeType.MENTIONS))
        r = g.validate()
        assert r.valid

    def test_invalid_schema_raises_error(self):
        g = KnowledgeGraph()
        g._add_node(GraphNode("ENTITY:a", GraphNodeType.ENTITY, "a", "A"))
        g._add_node(GraphNode("ENTITY:b", GraphNodeType.ENTITY, "b", "B"))
        g._add_edge(GraphEdge("ENTITY:a", "ENTITY:b", EdgeType.MENTIONS))
        r = g.validate()
        assert not r.valid
        assert len(r.errors) >= 1

    def test_orphan_nodes_detected(self):
        g = KnowledgeGraph()
        g._add_node(GraphNode("ENTITY:a", GraphNodeType.ENTITY, "a", "A"))
        r = g.validate()
        assert len(r.orphan_nodes) >= 1

    def test_report_summary(self):
        r = GraphValidationReport(valid=True, node_count=5, edge_count=3)
        assert "Valid" in r.summary


# ── Traversal Options Tests ──

class TestTraversalOptions:
    def test_stop_on_types(self):
        opts = TraversalOptions(stop_on_types={GraphNodeType.DEAL})
        n = GraphNode("DEAL:d", GraphNodeType.DEAL)
        assert opts.should_stop_on(n)

    def test_minimum_confidence(self):
        opts = TraversalOptions(minimum_confidence=0.5)
        e = GraphEdge("a", "b", EdgeType.MENTIONS, confidence=0.3)
        assert not opts.should_traverse_edge(e)

    def test_filter_edge_types(self):
        opts = TraversalOptions(allowed_edge_types={EdgeType.SUPPORTS})
        e = GraphEdge("a", "b", EdgeType.MENTIONS)
        assert not opts.should_traverse_edge(e)


# ── GraphBuilder Tests ──

class TestGraphBuilder:
    def test_build_generates_stable_ids(self):
        e = BusinessEntity(ET.COMPANY, "Test"); e.id = "780527855675"
        g = GraphBuilder.build("doc-1", entities=[e])
        assert g.exists("ENTITY:780527855675")

    def test_build_sets_provenance(self):
        e = BusinessEntity(ET.COMPANY, "Test"); e.id = "e-1"
        g = GraphBuilder.build("doc-1", entities=[e])
        node = g.node("ENTITY:e-1")
        assert node is not None
        assert node.provenance is not None

    def test_build_with_deal(self):
        g = GraphBuilder.build("doc-1", deal_id="deal-1")
        assert g.exists("DEAL:deal-1")

    def test_build_with_agreement(self):
        g = GraphBuilder.build("doc-1", agreement_id="ag-1", agreement_participants=[])
        assert g.exists("AGREEMENT:ag-1")

    def test_builder_version(self):
        g = GraphBuilder.build("doc-1")
        assert g.graph_version == 1


# ── Path Explanation Tests ──

class TestPathExplanation:
    def test_path_has_explanation(self):
        e1 = BusinessEntity(ET.COMPANY, "A"); e1.id = "e1"
        e2 = BusinessEntity(ET.COMPANY, "B"); e2.id = "e2"
        g = GraphBuilder.build("doc-1", entities=[e1, e2], deal_id="d-1")
        path = g.find_path("ENTITY:e1", "DEAL:d-1")
        assert path is not None
        assert path.explanation is not None
        assert len(path.explanation.evidence) >= 1


# ── Validation Report Tests ──

class TestValidationReport:
    def test_built_graph_is_valid(self):
        e = BusinessEntity(ET.COMPANY, "T"); e.id = "t-1"
        g = GraphBuilder.build("doc-1", entities=[e])
        r = g.validate()
        assert r.valid or len(r.errors) == 0


# ── Workspace Tests ──

class TestWorkspace:
    def test_workspace_resolve(self):
        g = GraphBuilder.build("d-1", deal_id="de-1")
        ws = WorkspaceGraph(root_graph=g, selected_node_ids={"DEAL:de-1", "DOCUMENT:d-1"})
        r = ws.resolve()
        assert r is not None
        assert r.node_count >= 2


# ── Metrics Tests ──

class TestMetrics:
    def test_metrics(self):
        g = GraphBuilder.build("d-1")
        m = g.metrics()
        assert m["nodes"] >= 1
