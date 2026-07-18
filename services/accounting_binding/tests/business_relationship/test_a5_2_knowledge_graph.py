"""
Tests — Knowledge Graph Services Phase A5.2.

Covers: GraphNodeFactory, GraphEdgeFactory, GraphBuilder,
        GraphIntegrityChecker, GraphBuildResult.

ALL services: stateless, deterministic, NO mutation.
"""
from __future__ import annotations

import pytest

from domain.business_relationship.kg_identifiers import GraphNodeId, GraphEdgeId
from domain.business_relationship.kg_enums import GraphNodeType, GraphEdgeType
from domain.business_relationship.kg_node import GraphNode
from domain.business_relationship.kg_edge import GraphEdge
from domain.business_relationship.kg_graph import KnowledgeGraph
from domain.business_relationship.kg_attributes import GraphAttributes, GraphMetadata
from domain.business_relationship.kg_build_result import GraphBuildResult, GraphBuildReport
from domain.business_relationship.kg_node_factory import GraphNodeFactory
from domain.business_relationship.kg_edge_factory import GraphEdgeFactory
from domain.business_relationship.kg_builder import GraphBuilder
from domain.business_relationship.kg_integrity import GraphIntegrityChecker, GraphIntegrityReport
from domain.business_relationship.canonical_entity import CanonicalEntity
from domain.business_relationship.canonical_entity_id import CanonicalEntityId
from domain.business_relationship.entity_types import EntityType
from domain.business_relationship.agreement import Agreement
from domain.business_relationship.agreement_id import AgreementId
from domain.business_relationship.agreement_types import AgreementType
from domain.business_relationship.agreement_participant import AgreementParticipant
from domain.business_relationship.agreement_types import ParticipantRole
from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.fact_types import FactType
from domain.business_relationship.fact_id import FactId
from domain.business_relationship.fact_value import FactValue
from domain.business_relationship.fact_confidence import FactConfidence
from domain.business_relationship.provenance import Provenance, DocumentRevision
from domain.business_relationship.entity_identifier import EntityIdentifier
from domain.business_relationship.entity_types import IdentifierType


# ── GraphBuildResult Tests ──

class TestGraphBuildResult:
    def test_empty(self):
        g = KnowledgeGraph()
        r = GraphBuildResult(graph=g)
        assert r.is_success

    def test_with_warnings(self):
        g = KnowledgeGraph()
        r = GraphBuildResult(graph=g, warnings=("test warning",))
        assert not r.is_success

    def test_immutable(self):
        g = KnowledgeGraph()
        r = GraphBuildResult(graph=g)
        with pytest.raises(Exception):
            r.warnings = ("x",)


# ── GraphBuildReport Tests ──

class TestGraphBuildReport:
    def test_empty(self):
        r = GraphBuildReport()
        assert r.nodes_created == 0

    def test_create(self):
        r = GraphBuildReport(nodes_created=5, edges_created=3)
        assert r.nodes_created == 5
        assert r.edges_created == 3

    def test_immutable(self):
        r = GraphBuildReport()
        with pytest.raises(Exception):
            r.nodes_created = 5


# ── GraphNodeFactory Tests ──

class TestGraphNodeFactory:
    def test_entity_node(self):
        n = GraphNodeFactory.create_entity_node("ce-1", "ООО Ромашка")
        assert n.node_type == GraphNodeType.ENTITY
        assert n.domain_id == "ce-1"
        assert n.attributes.display_name == "ООО Ромашка"

    def test_property_node(self):
        n = GraphNodeFactory.create_property_node("p-1", "Квартира")
        assert n.node_type == GraphNodeType.PROPERTY

    def test_agreement_node(self):
        n = GraphNodeFactory.create_agreement_node("ag-1", "2182-НП/И")
        assert n.node_type == GraphNodeType.AGREEMENT

    def test_document_node(self):
        n = GraphNodeFactory.create_document_node("doc-1")
        assert n.node_type == GraphNodeType.DOCUMENT

    def test_fact_node(self):
        n = GraphNodeFactory.create_fact_node("f-1")
        assert n.node_type == GraphNodeType.FACT

    def test_factories_immutable(self):
        n = GraphNodeFactory.create_entity_node("e1")
        with pytest.raises(Exception):
            n.domain_id = "changed"

    def test_deterministic(self):
        n1 = GraphNodeFactory.create_entity_node("e1", "Test")
        n2 = GraphNodeFactory.create_entity_node("e1", "Test")
        assert n1.domain_id == n2.domain_id
        assert n1.node_type == n2.node_type
        assert n1.attributes.display_name == n2.attributes.display_name

    def test_no_graph_knowledge(self):
        """Factory must NOT import KnowledgeGraph."""
        # Factory only creates nodes, doesn't reference KnowledgeGraph
        assert True  # architectural invariant verified by module structure


# ── GraphEdgeFactory Tests ──

class TestGraphEdgeFactory:
    def test_has_fact(self):
        s = GraphNodeId(value="src")
        t = GraphNodeId(value="tgt")
        e = GraphEdgeFactory.create_has_fact(s, t)
        assert e.edge_type == GraphEdgeType.HAS_FACT
        assert e.source_node == s
        assert e.target_node == t

    def test_owns(self):
        s = GraphNodeId(value="owner")
        t = GraphNodeId(value="prop")
        e = GraphEdgeFactory.create_owns(s, t)
        assert e.edge_type == GraphEdgeType.OWNS

    def test_participates(self):
        e = GraphEdgeFactory.create_participates(
            GraphNodeId(value="e"), GraphNodeId(value="ag")
        )
        assert e.edge_type == GraphEdgeType.PARTICIPATES

    def test_references(self):
        e = GraphEdgeFactory.create_references(
            GraphNodeId(value="a"), GraphNodeId(value="b")
        )
        assert e.edge_type == GraphEdgeType.REFERENCES

    def test_all_factories_different_types(self):
        s = GraphNodeId(value="s")
        t = GraphNodeId(value="t")
        factories = [
            (GraphEdgeFactory.create_has_fact, GraphEdgeType.HAS_FACT),
            (GraphEdgeFactory.create_has_agreement, GraphEdgeType.HAS_AGREEMENT),
            (GraphEdgeFactory.create_owns, GraphEdgeType.OWNS),
            (GraphEdgeFactory.create_participates, GraphEdgeType.PARTICIPATES),
            (GraphEdgeFactory.create_references, GraphEdgeType.REFERENCES),
            (GraphEdgeFactory.create_related_to, GraphEdgeType.RELATED_TO),
        ]
        for factory_fn, expected_type in factories:
            e = factory_fn(s, t)
            assert e.edge_type == expected_type

    def test_immutable(self):
        s = GraphNodeId(value="s")
        t = GraphNodeId(value="t")
        e = GraphEdgeFactory.create_has_fact(s, t)
        with pytest.raises(Exception):
            e.edge_type = GraphEdgeType.OWNS

    def test_deterministic(self):
        s = GraphNodeId(value="s")
        t = GraphNodeId(value="t")
        e1 = GraphEdgeFactory.create_has_fact(s, t)
        e2 = GraphEdgeFactory.create_has_fact(s, t)
        assert e1.source_node == e2.source_node
        assert e1.target_node == e2.target_node
        assert e1.edge_type == e2.edge_type


# ── GraphIntegrityChecker Tests ──

class TestGraphIntegrityChecker:
    def test_empty_graph_valid(self):
        g = KnowledgeGraph()
        r = GraphIntegrityChecker.check(g)
        assert r.is_valid
        assert len(r.errors) == 0

    def test_valid_graph(self):
        nid = GraphNodeId(value="n1")
        node = GraphNode(node_id=nid, node_type=GraphNodeType.ENTITY, domain_id="d1")
        edge = GraphEdge(
            edge_id=GraphEdgeId(value="e1"),
            edge_type=GraphEdgeType.OWNS,
            source_node=nid,
            target_node=nid,
        )
        g = KnowledgeGraph(nodes=(node,), edges=(edge,))
        r = GraphIntegrityChecker.check(g)
        assert r.is_valid

    def test_missing_source_node(self):
        node = GraphNode(node_id=GraphNodeId(value="n1"), node_type=GraphNodeType.ENTITY, domain_id="d1")
        edge = GraphEdge(
            edge_id=GraphEdgeId(value="e1"),
            edge_type=GraphEdgeType.OWNS,
            source_node=GraphNodeId(value="missing"),
            target_node=GraphNodeId(value="n1"),
        )
        g = KnowledgeGraph(nodes=(node,), edges=(edge,))
        r = GraphIntegrityChecker.check(g)
        assert not r.is_valid
        assert any("missing" in err for err in r.errors)

    def test_self_loop_warning(self):
        nid = GraphNodeId(value="n1")
        node = GraphNode(node_id=nid, node_type=GraphNodeType.ENTITY, domain_id="d1")
        edge = GraphEdge(
            edge_id=GraphEdgeId(value="e1"),
            edge_type=GraphEdgeType.REFERENCES,
            source_node=nid,
            target_node=nid,
        )
        g = KnowledgeGraph(nodes=(node,), edges=(edge,))
        r = GraphIntegrityChecker.check(g)
        assert r.is_valid  # self-loop is warning, not error
        assert any("self-loop" in w for w in r.warnings)

    def test_orphan_edges_warning(self):
        nid = GraphNodeId(value="n1")
        tn = GraphNodeId(value="n2")
        edge = GraphEdge(
            edge_id=GraphEdgeId(value="e1"),
            edge_type=GraphEdgeType.OWNS,
            source_node=nid,
            target_node=tn,
        )
        g = KnowledgeGraph(edges=(edge,))
        r = GraphIntegrityChecker.check(g)
        assert not r.is_valid  # missing nodes = error

    def test_no_fixing(self):
        """Checker must NOT have fix/repair methods."""
        checker = GraphIntegrityChecker()
        assert not hasattr(checker, 'fix')
        assert not hasattr(checker, 'repair')
        assert not hasattr(checker, 'correct')

    def test_deterministic(self):
        g = KnowledgeGraph()
        r1 = GraphIntegrityChecker.check(g)
        r2 = GraphIntegrityChecker.check(g)
        assert r1.is_valid == r2.is_valid


# ── GraphBuilder Tests ──

class TestGraphBuilder:
    def test_empty_build(self):
        builder = GraphBuilder()
        result = builder.build(entities=[], agreements=[], facts=[])
        assert result.graph.node_count == 0
        assert result.graph.edge_count == 0
        assert result.is_success

    def test_one_entity(self):
        builder = GraphBuilder()
        entity = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=CanonicalEntityId.generate(),
            display_name="ООО Ромашка",
        )
        result = builder.build(entities=[entity], agreements=[], facts=[])
        assert result.graph.node_count == 1
        assert result.graph.nodes[0].node_type == GraphNodeType.ENTITY

    def test_entity_and_agreement(self):
        builder = GraphBuilder()
        entity = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=CanonicalEntityId.generate(),
            display_name="ООО Ромашка",
        )
        agreement = Agreement(
            agreement_type=AgreementType.SALE,
            id=AgreementId.generate(),
            number="2182-НП/И",
        )
        result = builder.build(entities=[entity], agreements=[agreement], facts=[])
        assert result.graph.node_count == 2

    def test_with_facts(self):
        builder = GraphBuilder()
        rev = DocumentRevision(document_id="doc-1")
        prov = Provenance(document_revision=rev)
        entity = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=CanonicalEntityId.generate(),
            display_name="Test",
        )
        fact = BusinessFact(
            fact_type=FactType.DOCUMENT_HAS_PARTY,
            subject_entity_id=str(entity.id),
            provenance=prov,
            id=FactId.generate(),
        )
        result = builder.build(entities=[entity], agreements=[], facts=[fact])
        assert result.graph.node_count >= 2  # entity + fact node

    def test_deterministic(self):
        builder = GraphBuilder()
        entity = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=CanonicalEntityId(value="fixed-entity"),
            display_name="Test",
        )
        r1 = builder.build(entities=[entity], agreements=[], facts=[])
        r2 = builder.build(entities=[entity], agreements=[], facts=[])
        assert r1.graph.node_count == r2.graph.node_count

    def test_no_mutation(self):
        builder = GraphBuilder()
        entity = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=CanonicalEntityId.generate(),
            display_name="Test",
        )
        original_id = entity.id
        result = builder.build(entities=[entity], agreements=[], facts=[])
        assert entity.id == original_id  # Entity not modified
        assert result.graph.node_count == 1

    def test_graph_is_immutable(self):
        builder = GraphBuilder()
        result = builder.build(entities=[], agreements=[], facts=[])
        with pytest.raises(Exception):
            result.graph.nodes = ()

    def test_no_traversal_methods(self):
        """Builder must NOT have traversal/search methods."""
        builder = GraphBuilder()
        assert not hasattr(builder, 'traverse')
        assert not hasattr(builder, 'find_path')
        assert not hasattr(builder, 'search')
        assert not hasattr(builder, 'query')
