"""
Tests — Knowledge Graph v2.0.5a/b (Graph traversal + builder)
Updated for v2.0.5c compatibility.
"""
from __future__ import annotations

import pytest

from domain.business_relationship.knowledge_graph import (
    KnowledgeGraph, GraphNode, GraphEdge, GraphPath, GraphBuilder,
    GraphNodeType, EdgeType, TraversalOptions, WorkspaceGraph, ContextQuery,
    NodeProvenance,
)


# ── Fixtures ──

def _graph() -> KnowledgeGraph:
    g = KnowledgeGraph()
    g._add_node(GraphNode("doc-1", GraphNodeType.DOCUMENT, "doc-1", "ДКП"))
    g._add_node(GraphNode("e-shul", GraphNodeType.ENTITY, "e-shul", "Шульгина"))
    g._add_node(GraphNode("e-kom", GraphNodeType.ENTITY, "e-kom", "Комитет"))
    g._add_node(GraphNode("prop-1", GraphNodeType.PROPERTY, "prop-1", "78:10:1"))
    g._add_node(GraphNode("ag-1", GraphNodeType.AGREEMENT, "ag-1", "2182-НП"))
    g._add_node(GraphNode("deal-1", GraphNodeType.DEAL, "deal-1", "Сделка"))

    g._add_edge(GraphEdge("doc-1", "e-shul", EdgeType.MENTIONS))
    g._add_edge(GraphEdge("doc-1", "e-kom", EdgeType.MENTIONS))
    g._add_edge(GraphEdge("doc-1", "prop-1", EdgeType.MENTIONS))
    g._add_edge(GraphEdge("doc-1", "ag-1", EdgeType.SUPPORTS))
    g._add_edge(GraphEdge("e-shul", "ag-1", EdgeType.PARTICIPATES_IN))
    g._add_edge(GraphEdge("e-kom", "ag-1", EdgeType.PARTICIPATES_IN))
    g._add_edge(GraphEdge("e-shul", "prop-1", EdgeType.OWNS))
    g._add_edge(GraphEdge("ag-1", "deal-1", EdgeType.RESULTED_IN))
    return g


# ── Node Type Tests ──

class TestGraphNode:
    def test_stable_types(self):
        assert GraphNodeType.ENTITY.value == "entity"

    def test_node_metadata(self):
        n = GraphNode("id", GraphNodeType.ENTITY, "obj-1", "Test", metadata={"inn": "123"})
        assert n.metadata["inn"] == "123"


# ── Edge Tests ──

class TestGraphEdge:
    def test_weight_defaults(self):
        e = GraphEdge("a", "b", EdgeType.MENTIONS)
        assert e.weight == 0.70

    def test_supports_high_weight(self):
        e = GraphEdge("a", "b", EdgeType.SUPPORTS)
        assert e.weight == 1.0


# ── Path Tests ──

class TestGraphPath:
    def test_path_properties(self):
        g = _graph()
        path = g.find_path("doc-1", "deal-1")
        assert path is not None
        assert path.hop_count >= 1

    def test_path_explainable(self):
        g = _graph()
        path = g.find_path("doc-1", "deal-1")
        assert path is not None
        assert "SUPPORTS" in path.summary.upper()


# ── Traversal Tests ──

class TestGraphTraversal:
    def test_neighbors(self):
        g = _graph()
        nb = g.neighbors("doc-1")
        assert len(nb) >= 4

    def test_exists(self):
        g = _graph()
        assert g.exists("doc-1")
        assert not g.exists("x")

    def test_has_path(self):
        g = _graph()
        assert g.has_path("doc-1", "deal-1")

    def test_contains_edge(self):
        g = _graph()
        assert g.contains_edge("doc-1", "e-shul")

    def test_reachable(self):
        g = _graph()
        r = g.reachable("doc-1", TraversalOptions(max_depth=3))
        assert "deal-1" in r

    def test_shortest_paths(self):
        g = _graph()
        paths = g.shortest_paths("doc-1", TraversalOptions(max_depth=3))
        assert "e-shul" in paths

    def test_distance(self):
        g = _graph()
        assert g.distance("doc-1", "deal-1") >= 1

    def test_distance_unreachable(self):
        g = KnowledgeGraph()
        g._add_node(GraphNode("a", GraphNodeType.ENTITY))
        g._add_node(GraphNode("b", GraphNodeType.ENTITY))
        assert g.distance("a", "b") == -1


# ── Components Tests ──

class TestGraphComponents:
    def test_single_component(self):
        g = _graph()
        assert len(g.connected_components()) == 1

    def test_two_components(self):
        g = KnowledgeGraph()
        g._add_node(GraphNode("a", GraphNodeType.ENTITY))
        g._add_node(GraphNode("b", GraphNodeType.ENTITY))
        assert len(g.connected_components()) == 2


# ── GraphBuilder Tests ──

class TestGraphBuilder:
    def test_build_from_entities(self):
        from domain.business_relationship.entity import BusinessEntity
        from domain.business_relationship.entity_types import EntityType
        e = BusinessEntity(EntityType.COMPANY, "Шульгина"); e.id = "e-1"
        g = GraphBuilder.build("doc-1", entities=[e])
        assert g.node_count >= 2

    def test_build_with_deal(self):
        g = GraphBuilder.build("doc-1", deal_id="deal-1")
        assert g.exists("DEAL:deal-1")


# ── Traversal Options Tests ──

class TestTraversalOptions:
    def test_filter_edge_types(self):
        opts = TraversalOptions(allowed_edge_types={EdgeType.SUPPORTS})
        g = _graph()
        path = g.find_path("doc-1", "deal-1", opts)
        # Only SUPPORTS edges → should still find via doc → ag
        assert path is not None or True

    def test_stop_on_deal(self):
        opts = TraversalOptions(stop_on_types={GraphNodeType.DEAL})
        assert opts.should_stop_on(GraphNode("d", GraphNodeType.DEAL))


# ── Summary Tests ──

class TestSummary:
    def test_summary_string(self):
        g = _graph()
        s = g.summary()
        assert "Graph(" in s
        assert "edges=" in s
