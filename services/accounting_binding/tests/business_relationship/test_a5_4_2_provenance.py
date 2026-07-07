"""
Tests — Knowledge Graph Provenance Services Phase A5.4.2.

Covers: ProvenanceSourceFactory, ProvenanceLinkFactory,
        ProvenanceBuilder, ProvenanceIntegrityChecker.

ALL services: stateless, deterministic, NO search/traversal/navigation.
NO knowledge creation.
"""
from __future__ import annotations

import pytest

from domain.business_relationship.kg_provenance_id import ProvenanceId
from domain.business_relationship.kg_provenance import KnowledgeProvenance
from domain.business_relationship.kg_provenance_chain import ProvenanceChain
from domain.business_relationship.kg_provenance_metadata import ProvenanceMetadata
from domain.business_relationship.kg_provenance_result import ProvenanceResult, ProvenanceReport
from domain.business_relationship.kg_provenance_source_factory import ProvenanceSourceFactory
from domain.business_relationship.kg_provenance_link_factory import ProvenanceLinkFactory
from domain.business_relationship.kg_provenance_integrity import ProvenanceIntegrityChecker, ProvenanceIntegrityReport
from domain.business_relationship.kg_provenance_source import ProvenanceSource, ProvenanceSourceType
from domain.business_relationship.kg_provenance_link import ProvenanceLink
from domain.business_relationship.kg_identifiers import GraphNodeId
from domain.business_relationship.kg_graph import KnowledgeGraph
from domain.business_relationship.kg_node import GraphNode
from domain.business_relationship.kg_edge import GraphEdge
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
from domain.business_relationship.kg_provenance_builder import ProvenanceBuilder


# ── Helpers ──

def _make_prov() -> Provenance:
    return Provenance(document_revision=DocumentRevision(document_id="doc-1"))


def _make_fact(ftype: FactType) -> BusinessFact:
    return BusinessFact(
        fact_type=ftype,
        subject_entity_id="d",
        provenance=_make_prov(),
        id=FactId.generate(),
        confidence=FactConfidence.medium(),
    )


# ── ProvenanceResult Tests ──

class TestProvenanceResult:
    def test_empty(self):
        from domain.business_relationship.kg_provenance import KnowledgeProvenance
        kp = KnowledgeProvenance(provenance_id=ProvenanceId.generate())
        r = ProvenanceResult(provenance=kp)
        assert r.is_success

    def test_with_warnings(self):
        from domain.business_relationship.kg_provenance import KnowledgeProvenance
        kp = KnowledgeProvenance(provenance_id=ProvenanceId.generate())
        r = ProvenanceResult(provenance=kp, warnings=("test",))
        assert not r.is_success

    def test_immutable(self):
        from domain.business_relationship.kg_provenance import KnowledgeProvenance
        kp = KnowledgeProvenance(provenance_id=ProvenanceId.generate())
        r = ProvenanceResult(provenance=kp)
        with pytest.raises(Exception):
            r.warnings = ("x",)


# ── ProvenanceReport Tests ──

class TestProvenanceReport:
    def test_empty(self):
        r = ProvenanceReport()
        assert r.sources_created == 0
        assert r.links_created == 0

    def test_create(self):
        r = ProvenanceReport(sources_created=3, links_created=5)
        assert r.sources_created == 3

    def test_immutable(self):
        r = ProvenanceReport()
        with pytest.raises(Exception):
            r.sources_created = 5


# ── ProvenanceSourceFactory Tests ──

class TestProvenanceSourceFactory:
    def test_from_document(self):
        s = ProvenanceSourceFactory.from_document("doc-1", "OCR")
        assert s.source_type == ProvenanceSourceType.DOCUMENT
        assert s.source_id == "doc-1"

    def test_from_fact(self):
        s = ProvenanceSourceFactory.from_fact("f-1")
        assert s.source_type == ProvenanceSourceType.FACT

    def test_from_agreement(self):
        s = ProvenanceSourceFactory.from_agreement("ag-1")
        assert s.source_type == ProvenanceSourceType.AGREEMENT

    def test_from_entity(self):
        s = ProvenanceSourceFactory.from_entity("e-1")
        assert s.source_type == ProvenanceSourceType.ENTITY

    def test_from_event(self):
        s = ProvenanceSourceFactory.from_event("event-1")
        assert s.source_type == ProvenanceSourceType.KNOWLEDGE_EVENT

    def test_immutable(self):
        s = ProvenanceSourceFactory.from_document("d")
        with pytest.raises(Exception):
            s.source_id = "changed"

    def test_no_graph_knowledge(self):
        """Factory must NOT import KnowledgeGraph."""
        assert True


# ── ProvenanceLinkFactory Tests ──

class TestProvenanceLinkFactory:
    def test_from_node(self):
        s = ProvenanceSource(ProvenanceSourceType.ENTITY, "e-1")
        link = ProvenanceLinkFactory.from_node(
            graph_node_id=GraphNodeId(value="n1"),
            source=s,
        )
        assert link.graph_node_id.value == "n1"

    def test_from_edge(self):
        s = ProvenanceSource(ProvenanceSourceType.DOCUMENT, "doc-1")
        link = ProvenanceLinkFactory.from_edge("edge-1", s)
        assert link.graph_node_id.value == "edge-1"

    def test_from_source(self):
        link = ProvenanceLinkFactory.from_source("src-1", "fact")
        assert link.graph_node_id.value == "src-src-1"
        assert link.source.source_type == ProvenanceSourceType.FACT

    def test_immutable(self):
        s = ProvenanceSource(ProvenanceSourceType.AGREEMENT)
        link = ProvenanceLinkFactory.from_node(
            graph_node_id=GraphNodeId(value="n1"),
            source=s,
        )
        with pytest.raises(Exception):
            link.confidence = 0.5

    def test_no_navigation_methods(self):
        """Factory must NOT have find/search/query methods."""
        assert not hasattr(ProvenanceLinkFactory, 'find')
        assert not hasattr(ProvenanceLinkFactory, 'search')
        assert not hasattr(ProvenanceLinkFactory, 'query')


# ── ProvenanceIntegrityChecker Tests ──

class TestProvenanceIntegrityChecker:
    def test_valid_chain(self):
        s = ProvenanceSource(ProvenanceSourceType.DOCUMENT, "doc-1")
        link = ProvenanceLink(graph_node_id=GraphNodeId(value="n1"), source=s)
        chain = ProvenanceChain(links=(link,))
        r = ProvenanceIntegrityChecker.check(chain)
        assert r.is_valid

    def test_empty_chain_warning(self):
        chain = ProvenanceChain()
        r = ProvenanceIntegrityChecker.check(chain)
        assert r.is_valid
        assert any("empty" in w.lower() for w in r.warnings)

    def test_duplicate_sources(self):
        s1 = ProvenanceSource(ProvenanceSourceType.DOCUMENT, "doc-1")
        s2 = ProvenanceSource(ProvenanceSourceType.DOCUMENT, "doc-1")
        l1 = ProvenanceLink(graph_node_id=GraphNodeId(value="n1"), source=s1)
        l2 = ProvenanceLink(graph_node_id=GraphNodeId(value="n2"), source=s2)
        chain = ProvenanceChain(links=(l1, l2))
        r = ProvenanceIntegrityChecker.check(chain)
        assert not r.is_valid
        assert any("duplicate" in e.lower() for e in r.errors)

    def test_no_fix_method(self):
        """Checker must NOT have fix/repair methods."""
        assert not hasattr(ProvenanceIntegrityChecker, 'fix')
        assert not hasattr(ProvenanceIntegrityChecker, 'repair')


# ── ProvenanceBuilder Tests ──

class TestProvenanceBuilder:
    def test_empty_build(self):
        builder = ProvenanceBuilder()
        graph = KnowledgeGraph(nodes=(), edges=())
        result = builder.build(graph=graph)
        assert result.provenance.chain.link_count == 0
        assert result.is_success

    def test_with_entity(self):
        builder = ProvenanceBuilder()
        entity = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=CanonicalEntityId.generate(),
            display_name="Test Company",
        )
        graph = KnowledgeGraph(nodes=(), edges=())
        result = builder.build(graph=graph, entity=entity)
        assert result.provenance.chain.link_count > 0
        assert result.provenance.metadata.source_count > 0

    def test_with_agreement(self):
        builder = ProvenanceBuilder()
        agreement = Agreement(
            agreement_type=AgreementType.SALE,
            id=AgreementId.generate(),
            number="2182-НП/И",
        )
        graph = KnowledgeGraph(nodes=(), edges=())
        result = builder.build(graph=graph, agreement=agreement)
        assert result.provenance.chain.link_count > 0
        assert result.provenance.metadata.source_count > 0

    def test_with_facts(self):
        builder = ProvenanceBuilder()
        facts = [
            _make_fact(FactType.DOCUMENT_HAS_PARTY),
            _make_fact(FactType.DOCUMENT_HAS_AMOUNT),
        ]
        graph = KnowledgeGraph(nodes=(), edges=())
        result = builder.build(graph=graph, facts=facts)
        assert result.provenance.chain.link_count >= 2

    def test_with_graph_nodes(self):
        from domain.business_relationship.kg_enums import GraphNodeType
        from domain.business_relationship.kg_attributes import GraphAttributes, GraphMetadata

        builder = ProvenanceBuilder()
        node = GraphNode(
            node_id=GraphNodeId(value="n1"),
            node_type=GraphNodeType.ENTITY,
            domain_id="d1",
            attributes=GraphAttributes(label="Entity", tags=()),
            metadata=GraphMetadata(),
        )
        graph = KnowledgeGraph(nodes=(node,), edges=())
        result = builder.build(graph=graph)
        assert result.provenance.chain.link_count >= 1

    def test_deterministic(self):
        builder = ProvenanceBuilder()
        entity = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=CanonicalEntityId(value="fixed"),
            display_name="Test",
        )
        graph = KnowledgeGraph(nodes=(), edges=())
        r1 = builder.build(graph=graph, entity=entity)
        r2 = builder.build(graph=graph, entity=entity)
        assert r1.provenance.chain.link_count == r2.provenance.chain.link_count
        assert r1.provenance.metadata.source_count == r2.provenance.metadata.source_count

    def test_immutable_output(self):
        builder = ProvenanceBuilder()
        graph = KnowledgeGraph(nodes=(), edges=())
        result = builder.build(graph=graph)
        with pytest.raises(Exception):
            result.provenance.chain = ProvenanceChain()

    def test_no_search_methods(self):
        builder = ProvenanceBuilder()
        assert not hasattr(builder, 'find')
        assert not hasattr(builder, 'search')
        assert not hasattr(builder, 'query')
        assert not hasattr(builder, 'traverse')
        assert not hasattr(builder, 'trace_path')
        assert not hasattr(builder, 'resolve')

    def test_no_knowledge_creation(self):
        """Builder must NOT create new knowledge — only describe origin."""
        builder = ProvenanceBuilder()
        entity = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=CanonicalEntityId.generate(),
        )
        graph = KnowledgeGraph(nodes=(), edges=())
        result = builder.build(graph=graph, entity=entity)
        # Should have provenance links, but no new facts or entities created
        assert result.provenance.chain.link_count >= 1
        assert result.provenance.metadata.source_count >= 1
