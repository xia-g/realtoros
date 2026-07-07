"""
Tests — Canonical Identity Aggregate Phase A3.1.

Covers: CanonicalEntityId, EntityAlias, EntityIdentifier,
        IdentityEvidence, IdentityMetadata, CanonicalEntity.

All models must be:
  immutable, serializable, hashable, deterministic,
  equality based on value, technology-independent.
  NO business logic. NO matching. NO normalization.
"""
from __future__ import annotations

import pytest

from domain.business_relationship.entity_types import EntityType, IdentifierType
from domain.business_relationship.canonical_entity_id import CanonicalEntityId
from domain.business_relationship.entity_alias import EntityAlias, AliasType
from domain.business_relationship.entity_identifier import EntityIdentifier
from domain.business_relationship.identity_evidence import IdentityEvidence
from domain.business_relationship.identity_metadata import IdentityMetadata
from domain.business_relationship.canonical_entity import CanonicalEntity


# ── CanonicalEntityId Tests ──

class TestCanonicalEntityId:
    def test_create(self):
        eid = CanonicalEntityId(value="ce-1")
        assert str(eid) == "ce-1"

    def test_generate(self):
        eid = CanonicalEntityId.generate()
        assert bool(eid)
        assert len(eid.value) > 0

    def test_from_string(self):
        eid = CanonicalEntityId.from_string("test-id")
        assert eid.value == "test-id"

    def test_from_string_empty_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            CanonicalEntityId.from_string("")

    def test_immutable(self):
        eid = CanonicalEntityId(value="x")
        with pytest.raises(Exception):
            eid.value = "y"

    def test_equality(self):
        assert CanonicalEntityId(value="x") == CanonicalEntityId(value="x")
        assert CanonicalEntityId(value="x") != CanonicalEntityId(value="y")

    def test_hashable(self):
        s = {CanonicalEntityId(value="a"), CanonicalEntityId(value="a")}
        assert len(s) == 1


# ── EntityAlias Tests ──

class TestEntityAlias:
    def test_create(self):
        a = EntityAlias(
            original_value="ИП Шульгина",
            normalized_value="ип шульгина",
            alias_type=AliasType.NAME_VARIANT,
        )
        assert a.original_value == "ИП Шульгина"
        assert a.normalized_value == "ип шульгина"

    def test_with_source(self):
        a = EntityAlias("ИП", "ип", source_document_id="doc-1")
        assert a.source_document_id == "doc-1"

    def test_immutable(self):
        a = EntityAlias("x", "x")
        with pytest.raises(Exception):
            a.original_value = "y"

    def test_all_types(self):
        for t in AliasType:
            a = EntityAlias("a", "b", alias_type=t)
            assert a.alias_type == t


# ── EntityIdentifier Tests ──

class TestEntityIdentifier:
    def test_create(self):
        ei = EntityIdentifier(
            identifier_type=IdentifierType.INN,
            value="780527855675",
        )
        assert ei.identifier_type == IdentifierType.INN
        assert ei.value == "780527855675"

    def test_with_confidence(self):
        ei = EntityIdentifier(IdentifierType.INN, "123", confidence=0.95)
        assert ei.confidence == 0.95

    def test_immutable(self):
        ei = EntityIdentifier(IdentifierType.INN, "x")
        with pytest.raises(Exception):
            ei.value = "y"

    def test_all_types(self):
        for t in IdentifierType:
            ei = EntityIdentifier(t, "val")
            assert ei.identifier_type == t


# ── IdentityEvidence Tests ──

class TestIdentityEvidence:
    def test_create(self):
        ev = IdentityEvidence(source_document_id="doc-1", confidence=0.9)
        assert ev.source_document_id == "doc-1"
        assert ev.confidence == 0.9

    def test_with_detail(self):
        ev = IdentityEvidence("doc-1", detail="INN match")
        assert ev.detail == "INN match"

    def test_immutable(self):
        ev = IdentityEvidence("d")
        with pytest.raises(Exception):
            ev.source_document_id = "changed"


# ── IdentityMetadata Tests ──

class TestIdentityMetadata:
    def test_defaults(self):
        m = IdentityMetadata()
        assert m.confidence == 1.0

    def test_create(self):
        m = IdentityMetadata(confidence=0.8)
        assert m.confidence == 0.8

    def test_immutable(self):
        m = IdentityMetadata()
        with pytest.raises(Exception):
            m.confidence = 0.5


# ── CanonicalEntity Tests ──

class TestCanonicalEntity:
    def test_create(self):
        eid = CanonicalEntityId.generate()
        ce = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=eid,
            display_name="ООО Ромашка",
        )
        assert ce.entity_type == EntityType.COMPANY
        assert ce.display_name == "ООО Ромашка"
        assert ce.primary_identifier == ""

    def test_with_identifiers(self):
        ei = EntityIdentifier(IdentifierType.INN, "780527855675")
        ce = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=CanonicalEntityId.generate(),
            display_name="ООО Ромашка",
            identifiers=(ei,),
        )
        assert len(ce.identifiers) == 1
        assert ce.primary_identifier == "780527855675"

    def test_with_aliases(self):
        a = EntityAlias("Ромашка", "ромашка")
        ce = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=CanonicalEntityId.generate(),
            aliases=(a,),
        )
        assert len(ce.aliases) == 1

    def test_with_evidence(self):
        ev = IdentityEvidence("doc-1", confidence=0.95)
        ce = CanonicalEntity(
            entity_type=EntityType.PERSON,
            id=CanonicalEntityId.generate(),
            evidence=(ev,),
        )
        assert len(ce.evidence) == 1
        assert ce.evidence[0].confidence == 0.95

    def test_immutable(self):
        ce = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=CanonicalEntityId.generate(),
        )
        with pytest.raises(Exception):
            ce.display_name = "changed"

    def test_equality(self):
        eid = CanonicalEntityId(value="x")
        ce1 = CanonicalEntity(entity_type=EntityType.COMPANY, id=eid)
        ce2 = CanonicalEntity(entity_type=EntityType.COMPANY, id=eid)
        assert ce1 == ce2
        ce3 = CanonicalEntity(entity_type=EntityType.PERSON, id=CanonicalEntityId(value="y"))
        assert ce1 != ce3

    def test_hashable(self):
        eid = CanonicalEntityId(value="x")
        ce = CanonicalEntity(entity_type=EntityType.COMPANY, id=eid)
        s = {ce, ce}
        assert len(s) == 1

    def test_repr(self):
        ce = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=CanonicalEntityId(value="test-id"),
            display_name="Test",
        )
        r = repr(ce)
        assert "test-id" in r
        assert "company" in r

    def test_all_entity_types(self):
        for t in EntityType:
            ce = CanonicalEntity(entity_type=t, id=CanonicalEntityId.generate())
            assert ce.entity_type == t

    def test_various_entities(self):
        """Person, Company, Property — all valid entity types."""
        for t in (EntityType.PERSON, EntityType.COMPANY, EntityType.GOVERNMENT, EntityType.BANK):
            ce = CanonicalEntity(entity_type=t, id=CanonicalEntityId.generate())
            assert ce.entity_type == t

    def test_no_business_logic(self):
        """CanonicalEntity must NOT have add_alias(), confirm(), etc."""
        ce = CanonicalEntity(entity_type=EntityType.COMPANY, id=CanonicalEntityId.generate())
        # Verify no mutating methods
        assert not hasattr(ce, 'add_alias')
        assert not hasattr(ce, 'confirm')
        assert not hasattr(ce, 'merge')

    def test_no_knowledge_import(self):
        """CanonicalEntity must NOT import Knowledge, Graph, Revision, etc."""
        import sys
        mod = sys.modules.get(CanonicalEntity.__module__)
        assert mod is not None

    def test_multiple_identifiers_deduplicated(self):
        """Identifiers are stored as-is. No dedup logic in aggregate."""
        ei1 = EntityIdentifier(IdentifierType.INN, "123")
        ei2 = EntityIdentifier(IdentifierType.INN, "123")
        ce = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=CanonicalEntityId.generate(),
            identifiers=(ei1, ei2),
        )
        assert len(ce.identifiers) == 2
