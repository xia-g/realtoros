"""
Tests — Graph Schema, Version, Diff, Snapshot, Metrics v2.0.5b+ (updated for 2.0.5c)
"""
from __future__ import annotations

import pytest

from domain.business_relationship.knowledge_graph import (
    KnowledgeGraph, GraphNode, GraphEdge, GraphNodeType, EdgeType, TraversalOptions,
)
from domain.business_relationship.graph_schema import GraphSchema, GraphValidationError
from domain.business_relationship.graph_version import GraphVersion, GraphDiff, GraphSnapshot


# ── Schema Tests ──

class TestGraphSchema:
    def test_valid_edge(self):
        GraphSchema.validate(GraphNodeType.DOCUMENT, GraphNodeType.ENTITY, EdgeType.MENTIONS)

    def test_invalid_edge_raises(self):
        with pytest.raises(GraphValidationError):
            GraphSchema.validate(GraphNodeType.ENTITY, GraphNodeType.ENTITY, EdgeType.MENTIONS)

    def test_is_valid(self):
        assert GraphSchema.is_valid(GraphNodeType.DOCUMENT, GraphNodeType.ENTITY, EdgeType.MENTIONS)
        assert not GraphSchema.is_valid(GraphNodeType.ENTITY, GraphNodeType.ENTITY, EdgeType.MENTIONS)


# ── Version Tests ──

class TestGraphVersion:
    def test_version_immutable(self):
        v = GraphVersion(version=1, node_count=5, edge_count=8)
        with pytest.raises(Exception):
            v.version = 2


# ── Diff Tests ──

class TestGraphDiff:
    def test_diff_added_nodes(self):
        g1 = KnowledgeGraph()
        g1._add_node(GraphNode("a", GraphNodeType.ENTITY))
        g2 = KnowledgeGraph()
        g2._add_node(GraphNode("a", GraphNodeType.ENTITY))
        g2._add_node(GraphNode("b", GraphNodeType.ENTITY))
        diff = GraphDiff.compare(g1, g2)
        assert "b" in diff.added_nodes
        assert diff.has_changes

    def test_diff_no_changes(self):
        g1 = KnowledgeGraph()
        g1._add_node(GraphNode("a", GraphNodeType.ENTITY))
        g2 = KnowledgeGraph()
        g2._add_node(GraphNode("a", GraphNodeType.ENTITY))
        diff = GraphDiff.compare(g1, g2)
        assert not diff.has_changes


# ── Snapshot Tests ──

class TestGraphSnapshot:
    def test_snapshot_from_graph(self):
        g = KnowledgeGraph()
        g._add_node(GraphNode("a", GraphNodeType.ENTITY, "a", "Test"))
        snap = GraphSnapshot.from_graph(g, document_id="doc-1")
        assert snap.document_id == "doc-1"
        assert "nodes" in snap.serialized_graph

    def test_snapshot_to_json(self):
        g = KnowledgeGraph()
        g._add_node(GraphNode("a", GraphNodeType.ENTITY, "a", "Test"))
        snap = GraphSnapshot.from_graph(g)
        j = snap.to_json()
        assert '"nodes"' in j


# ── Workspace Tests ──

class TestWorkspace:
    def test_workspace_resolve(self):
        g = KnowledgeGraph()
        g._add_node(GraphNode("a", GraphNodeType.ENTITY, "a", "A"))
        g._add_node(GraphNode("b", GraphNodeType.ENTITY, "b", "B"))
        from domain.business_relationship.knowledge_graph import WorkspaceGraph
        ws = WorkspaceGraph(root_graph=g, selected_node_ids={"a", "b"})
        r = ws.resolve()
        assert r is not None
        assert r.node_count == 2
