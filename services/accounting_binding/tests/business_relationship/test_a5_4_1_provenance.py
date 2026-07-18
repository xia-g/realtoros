"""
Tests — Knowledge Graph Provenance Model Phase A5.4.1.

All models: immutable, no logic, no build/trace/resolve/find.
NO Domain Services. NO algorithms.
"""
from __future__ import annotations

import pytest

from domain.business_relationship.kg_provenance_id import ProvenanceId
from domain.business_relationship.kg_provenance_source import ProvenanceSource, ProvenanceSourceType
from domain.business_relationship.kg_provenance_link import ProvenanceLink
from domain.business_relationship.kg_provenance_chain import ProvenanceChain
from domain.business_relationship.kg_provenance_metadata import ProvenanceMetadata
from domain.business_relationship.kg_provenance import KnowledgeProvenance
from domain.business_relationship.kg_identifiers import GraphNodeId


# ── ProvenanceId Tests ──

class TestProvenanceId:
    def test_generate(self):
        pid = ProvenanceId.generate()
        assert bool(pid)

    def test_from_string(self):
        pid = ProvenanceId.from_string("prov-1")
        assert pid.value == "prov-1"

    def test_from_string_empty_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            ProvenanceId.from_string("")

    def test_immutable(self):
        pid = ProvenanceId(value="x")
        with pytest.raises(Exception):
            pid.value = "y"

    def test_equality(self):
        assert ProvenanceId(value="x") == ProvenanceId(value="x")
        assert ProvenanceId(value="x") != ProvenanceId(value="y")

    def test_hashable(self):
        s = {ProvenanceId(value="a"), ProvenanceId(value="a")}
        assert len(s) == 1


# ── ProvenanceSource Tests ──

class TestProvenanceSourceType:
    def test_values(self):
        assert ProvenanceSourceType.DOCUMENT.value == "document"
        assert ProvenanceSourceType.FACT.value == "fact"
        assert ProvenanceSourceType.KNOWLEDGE_EVENT.value == "knowledge_event"

    def test_all(self):
        for t in ProvenanceSourceType:
            assert t.value


class TestProvenanceSource:
    def test_create(self):
        s = ProvenanceSource(
            source_type=ProvenanceSourceType.DOCUMENT,
            source_id="doc-1",
            description="OCR extraction",
        )
        assert s.source_type == ProvenanceSourceType.DOCUMENT
        assert s.source_id == "doc-1"

    def test_equality(self):
        s1 = ProvenanceSource(ProvenanceSourceType.FACT, "f-1")
        s2 = ProvenanceSource(ProvenanceSourceType.FACT, "f-1")
        assert s1 == s2

    def test_immutable(self):
        s = ProvenanceSource(ProvenanceSourceType.AGREEMENT)
        with pytest.raises(Exception):
            s.source_id = "changed"


# ── ProvenanceLink Tests ──

class TestProvenanceLink:
    def test_create(self):
        s = ProvenanceSource(ProvenanceSourceType.DOCUMENT, "doc-1")
        link = ProvenanceLink(
            graph_node_id=GraphNodeId(value="n1"),
            source=s,
            confidence=0.95,
        )
        assert link.graph_node_id.value == "n1"
        assert link.confidence == 0.95

    def test_default_confidence(self):
        s = ProvenanceSource(ProvenanceSourceType.FACT)
        link = ProvenanceLink(graph_node_id=GraphNodeId(value="n1"), source=s)
        assert link.confidence == 1.0

    def test_immutable(self):
        s = ProvenanceSource(ProvenanceSourceType.AGREEMENT)
        link = ProvenanceLink(graph_node_id=GraphNodeId(value="n1"), source=s)
        with pytest.raises(Exception):
            link.confidence = 0.5


# ── ProvenanceChain Tests ──

class TestProvenanceChain:
    def test_empty(self):
        chain = ProvenanceChain()
        assert chain.link_count == 0

    def test_one_source(self):
        s = ProvenanceSource(ProvenanceSourceType.DOCUMENT, "doc-1")
        link = ProvenanceLink(graph_node_id=GraphNodeId(value="n1"), source=s)
        chain = ProvenanceChain(links=(link,))
        assert chain.link_count == 1

    def test_multiple_sources(self):
        s1 = ProvenanceSource(ProvenanceSourceType.DOCUMENT, "doc-1")
        s2 = ProvenanceSource(ProvenanceSourceType.FACT, "f-1")
        l1 = ProvenanceLink(graph_node_id=GraphNodeId(value="n1"), source=s1)
        l2 = ProvenanceLink(graph_node_id=GraphNodeId(value="n2"), source=s2)
        chain = ProvenanceChain(links=(l1, l2))
        assert chain.link_count == 2

    def test_equality(self):
        s = ProvenanceSource(ProvenanceSourceType.AGREEMENT, "ag-1")
        link = ProvenanceLink(graph_node_id=GraphNodeId(value="n1"), source=s)
        c1 = ProvenanceChain(links=(link,))
        c2 = ProvenanceChain(links=(link,))
        assert c1 == c2

    def test_immutable(self):
        chain = ProvenanceChain()
        with pytest.raises(Exception):
            chain.links = ()


# ── ProvenanceMetadata Tests ──

class TestProvenanceMetadata:
    def test_empty(self):
        meta = ProvenanceMetadata()
        assert meta.source_count == 0
        assert meta.confidence == 1.0

    def test_create(self):
        meta = ProvenanceMetadata(source_count=3, confidence=0.85)
        assert meta.source_count == 3
        assert meta.confidence == 0.85

    def test_equality(self):
        from datetime import datetime
        dt = datetime.utcnow()
        m1 = ProvenanceMetadata(created_at=dt, source_count=2)
        m2 = ProvenanceMetadata(created_at=dt, source_count=2)
        assert m1 == m2

    def test_immutable(self):
        meta = ProvenanceMetadata()
        with pytest.raises(Exception):
            meta.source_count = 5


# ── KnowledgeProvenance Tests ──

class TestKnowledgeProvenance:
    def test_create(self):
        pid = ProvenanceId.generate()
        s = ProvenanceSource(ProvenanceSourceType.DOCUMENT, "doc-1")
        link = ProvenanceLink(graph_node_id=GraphNodeId(value="n1"), source=s)
        chain = ProvenanceChain(links=(link,))
        meta = ProvenanceMetadata(source_count=1)

        kp = KnowledgeProvenance(
            provenance_id=pid,
            chain=chain,
            metadata=meta,
        )
        assert kp.provenance_id == pid
        assert kp.chain.link_count == 1
        assert kp.metadata.source_count == 1

    def test_equality(self):
        from datetime import datetime
        dt = datetime.utcnow()
        pid = ProvenanceId(value="x")
        meta = ProvenanceMetadata(created_at=dt)
        kp1 = KnowledgeProvenance(provenance_id=pid, metadata=meta)
        kp2 = KnowledgeProvenance(provenance_id=pid, metadata=meta)
        assert kp1 == kp2

    def test_immutable(self):
        pid = ProvenanceId.generate()
        kp = KnowledgeProvenance(provenance_id=pid)
        with pytest.raises(Exception):
            kp.chain = ProvenanceChain()

    def test_no_build_methods(self):
        """KnowledgeProvenance must NOT have build/trace/resolve/collect/find methods."""
        pid = ProvenanceId.generate()
        kp = KnowledgeProvenance(provenance_id=pid)
        assert not hasattr(kp, 'build')
        assert not hasattr(kp, 'trace')
        assert not hasattr(kp, 'resolve')
        assert not hasattr(kp, 'calculate')
        assert not hasattr(kp, 'collect')
        assert not hasattr(kp, 'find')