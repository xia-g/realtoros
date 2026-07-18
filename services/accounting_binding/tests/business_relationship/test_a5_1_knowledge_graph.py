"""
Tests — Knowledge Graph Domain Model Phase A5.1.

All models: immutable, no logic, no add/traverse/validate/query.
NO Domain Services. NO algorithms.
"""
from __future__ import annotations

import pytest

from domain.business_relationship.kg_identifiers import GraphNodeId, GraphEdgeId
from domain.business_relationship.kg_enums import GraphNodeType, GraphEdgeType
from domain.business_relationship.kg_attributes import GraphAttributes, GraphMetadata
from domain.business_relationship.kg_node import GraphNode
from domain.business_relationship.kg_edge import GraphEdge
from domain.business_relationship.kg_graph import KnowledgeGraph


# ── GraphNodeId Tests ──

class TestGraphNodeId:
    def test_generate(self):
        nid = GraphNodeId.generate()
        assert bool(nid)

    def test_from_string(self):
        nid = GraphNodeId.from_string("n-1")
        assert nid.value == "n-1"

    def test_from_string_empty_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            GraphNodeId.from_string("")

    def test_immutable(self):
        nid = GraphNodeId(value="x")
        with pytest.raises(Exception):
            nid.value = "y"

    def test_equality(self):
        assert GraphNodeId(value="x") == GraphNodeId(value="x")
        assert GraphNodeId(value="x") != GraphNodeId(value="y")

    def test_hashable(self):
        s = {GraphNodeId(value="a"), GraphNodeId(value="a")}
        assert len(s) == 1


# ── GraphEdgeId Tests ──

class TestGraphEdgeId:
    def test_generate(self):
        eid = GraphEdgeId.generate()
        assert bool(eid)

    def test_from_string(self):
        eid = GraphEdgeId.from_string("e-1")
        assert eid.value == "e-1"

    def test_from_string_empty_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            GraphEdgeId.from_string("")

    def test_immutable(self):
        eid = GraphEdgeId(value="x")
        with pytest.raises(Exception):
            eid.value = "y"

    def test_equality(self):
        assert GraphEdgeId(value="x") == GraphEdgeId(value="x")
        assert GraphEdgeId(value="x") != GraphEdgeId(value="y")


# ── GraphNodeType Tests ──

class TestGraphNodeType:
    def test_values(self):
        assert GraphNodeType.ENTITY.value == "entity"
        assert GraphNodeType.PROPERTY.value == "property"
        assert GraphNodeType.DEAL.value == "deal"

    def test_all(self):
        for t in GraphNodeType:
            assert t.value


# ── GraphEdgeType Tests ──

class TestGraphEdgeType:
    def test_values(self):
        assert GraphEdgeType.OWNS.value == "owns"
        assert GraphEdgeType.REFERENCES.value == "references"

    def test_all(self):
        for t in GraphEdgeType:
            assert t.value


# ── GraphAttributes Tests ──

class TestGraphAttributes:
    def test_empty(self):
        a = GraphAttributes()
        assert a.label == ""

    def test_with_tags(self):
        a = GraphAttributes(label="Test", tags=("tag1", "tag2"))
        assert a.label == "Test"
        assert len(a.tags) == 2

    def test_immutable(self):
        a = GraphAttributes()
        with pytest.raises(Exception):
            a.label = "changed"


# ── GraphMetadata Tests ──

class TestGraphMetadata:
    def test_defaults(self):
        m = GraphMetadata()
        assert m.schema_version == 1

    def test_immutable(self):
        m = GraphMetadata()
        with pytest.raises(Exception):
            m.schema_version = 2


# ── GraphNode Tests ──

class TestGraphNode:
    def test_create(self):
        nid = GraphNodeId.generate()
        node = GraphNode(
            node_id=nid,
            node_type=GraphNodeType.ENTITY,
            domain_id="ce-1",
        )
        assert node.node_id == nid
        assert node.node_type == GraphNodeType.ENTITY
        assert node.domain_id == "ce-1"

    def test_with_attributes(self):
        attrs = GraphAttributes(label="ООО Ромашка")
        node = GraphNode(
            node_id=GraphNodeId.generate(),
            node_type=GraphNodeType.ORGANIZATION,
            domain_id="ce-1",
            attributes=attrs,
        )
        assert node.attributes.label == "ООО Ромашка"

    def test_immutable(self):
        node = GraphNode(
            node_id=GraphNodeId.generate(),
            node_type=GraphNodeType.ENTITY,
            domain_id="d",
        )
        with pytest.raises(Exception):
            node.domain_id = "changed"

    def test_equality(self):
        nid = GraphNodeId(value="x")
        meta = GraphMetadata()
        n1 = GraphNode(node_id=nid, node_type=GraphNodeType.ENTITY, domain_id="d", metadata=meta)
        n2 = GraphNode(node_id=nid, node_type=GraphNodeType.ENTITY, domain_id="d", metadata=meta)
        assert n1 == n2

    def test_all_types(self):
        for t in GraphNodeType:
            n = GraphNode(
                node_id=GraphNodeId.generate(),
                node_type=t,
                domain_id="d",
            )
            assert n.node_type == t


# ── GraphEdge Tests ──

class TestGraphEdge:
    def test_create(self):
        eid = GraphEdgeId.generate()
        sn = GraphNodeId(value="src")
        tn = GraphNodeId(value="tgt")
        edge = GraphEdge(
            edge_id=eid,
            edge_type=GraphEdgeType.OWNS,
            source_node=sn,
            target_node=tn,
        )
        assert edge.edge_id == eid
        assert edge.edge_type == GraphEdgeType.OWNS
        assert edge.source_node == sn
        assert edge.target_node == tn

    def test_immutable(self):
        edge = GraphEdge(
            edge_id=GraphEdgeId.generate(),
            edge_type=GraphEdgeType.REFERENCES,
            source_node=GraphNodeId(value="s"),
            target_node=GraphNodeId(value="t"),
        )
        with pytest.raises(Exception):
            edge.edge_type = GraphEdgeType.OWNS

    def test_equality(self):
        eid = GraphEdgeId(value="e1")
        sn = GraphNodeId(value="s")
        tn = GraphNodeId(value="t")
        meta = GraphMetadata()
        e1 = GraphEdge(edge_id=eid, edge_type=GraphEdgeType.HAS_FACT, source_node=sn, target_node=tn, metadata=meta)
        e2 = GraphEdge(edge_id=eid, edge_type=GraphEdgeType.HAS_FACT, source_node=sn, target_node=tn, metadata=meta)
        assert e1 == e2

    def test_all_types(self):
        sn = GraphNodeId(value="s")
        tn = GraphNodeId(value="t")
        for t in GraphEdgeType:
            e = GraphEdge(edge_id=GraphEdgeId.generate(), edge_type=t, source_node=sn, target_node=tn)
            assert e.edge_type == t


# ── KnowledgeGraph Tests ──

class TestKnowledgeGraph:
    def test_empty(self):
        g = KnowledgeGraph()
        assert g.node_count == 0
        assert g.edge_count == 0

    def test_with_node(self):
        node = GraphNode(
            node_id=GraphNodeId.generate(),
            node_type=GraphNodeType.ENTITY,
            domain_id="ce-1",
        )
        g = KnowledgeGraph(nodes=(node,))
        assert g.node_count == 1

    def test_with_edge(self):
        sn = GraphNodeId(value="src")
        tn = GraphNodeId(value="tgt")
        edge = GraphEdge(
            edge_id=GraphEdgeId.generate(),
            edge_type=GraphEdgeType.OWNS,
            source_node=sn,
            target_node=tn,
        )
        g = KnowledgeGraph(edges=(edge,))
        assert g.edge_count == 1

    def test_multiple_nodes(self):
        nodes = tuple(
            GraphNode(node_id=GraphNodeId.generate(), node_type=GraphNodeType.ENTITY, domain_id=f"ce-{i}")
            for i in range(5)
        )
        g = KnowledgeGraph(nodes=nodes)
        assert g.node_count == 5

    def test_immutable(self):
        g = KnowledgeGraph()
        with pytest.raises(Exception):
            g.nodes = (GraphNode(
                node_id=GraphNodeId.generate(), node_type=GraphNodeType.ENTITY, domain_id="d"
            ),)

    def test_equality(self):
        meta = GraphMetadata()
        g1 = KnowledgeGraph(metadata=meta)
        g2 = KnowledgeGraph(metadata=meta)
        assert g1 == g2

    def test_no_add_method(self):
        g = KnowledgeGraph()
        assert not hasattr(g, 'add_node')
        assert not hasattr(g, 'add_edge')
        assert not hasattr(g, 'connect')
        assert not hasattr(g, 'traverse')
        assert not hasattr(g, 'validate')
        assert not hasattr(g, 'query')
        assert not hasattr(g, 'find')
        assert not hasattr(g, 'build')
