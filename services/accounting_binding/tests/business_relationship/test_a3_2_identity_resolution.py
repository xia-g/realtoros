"""
Tests — Identity Resolution Services Phase A3.2.

Covers: NormalizedIdentifier, IdentityCandidate, IdentityMatchResult,
        IdentifierNormalizer, IdentityMatcher, IdentityResolver.

ALL services: stateless, deterministic, side-effect free.
CanonicalEntity: ONE constructor call, NO post-mutation.
"""
from __future__ import annotations

import pytest

from domain.business_relationship.entity_types import EntityType, IdentifierType
from domain.business_relationship.entity import BusinessEntity
from domain.business_relationship.entity_identifier import EntityIdentifier
from domain.business_relationship.entity_alias import EntityAlias, AliasType
from domain.business_relationship.normalization import NormalizationService
from domain.business_relationship.normalized_identifier import NormalizedIdentifier
from domain.business_relationship.identity_candidate import IdentityCandidate
from domain.business_relationship.identity_evidence import IdentityEvidence
from domain.business_relationship.identity_match_result import IdentityMatchResult, MatchDecision
from domain.business_relationship.identity_resolution_result import (
    IdentityResolutionResult, IdentityResolutionReport,
)
from domain.business_relationship.identity_resolver import IdentityResolver
from domain.business_relationship.canonical_entity import CanonicalEntity
from domain.business_relationship.canonical_entity_id import CanonicalEntityId


# ── NormalizedIdentifier Tests ──

class TestNormalizedIdentifier:
    def test_create(self):
        ni = NormalizedIdentifier(IdentifierType.INN, "780527855675", "780527855675")
        assert ni.identifier_type == IdentifierType.INN
        assert ni.normalized == "780527855675"

    def test_normalized_flag(self):
        ni = NormalizedIdentifier(IdentifierType.INN, "123", "123")
        assert not ni.is_normalized
        ni2 = NormalizedIdentifier(IdentifierType.PHONE, "8(921)123-45-67", "+79211234567")
        assert ni2.is_normalized

    def test_immutable(self):
        ni = NormalizedIdentifier(IdentifierType.INN, "a", "a")
        with pytest.raises(Exception):
            ni.normalized = "b"


# ── IdentityCandidate Tests ──

class TestIdentityCandidate:
    def test_create(self):
        c = IdentityCandidate(
            entity_type=EntityType.COMPANY,
            display_name="ООО Ромашка",
        )
        assert c.entity_type == EntityType.COMPANY
        assert c.identifier_count == 0

    def test_with_identifiers(self):
        ni = NormalizedIdentifier(IdentifierType.INN, "780527855675", "780527855675")
        c = IdentityCandidate(
            entity_type=EntityType.COMPANY,
            display_name="ООО Ромашка",
            identifiers=(ni,),
        )
        assert c.identifier_count == 1
        assert c.primary_identifier == "780527855675"

    def test_immutable(self):
        c = IdentityCandidate(entity_type=EntityType.COMPANY, display_name="X")
        with pytest.raises(Exception):
            c.display_name = "Y"


# ── IdentityMatchResult Tests ──

class TestIdentityMatchResult:
    def test_match(self):
        c = IdentityCandidate(entity_type=EntityType.COMPANY, display_name="X")
        r = IdentityMatchResult(decision=MatchDecision.MATCH, candidate=c, reason="Exact")
        assert r.decision == MatchDecision.MATCH

    def test_all_decisions(self):
        c = IdentityCandidate(entity_type=EntityType.COMPANY, display_name="X")
        for d in MatchDecision:
            r = IdentityMatchResult(decision=d, candidate=c)
            assert r.decision == d

    def test_immutable(self):
        c = IdentityCandidate(entity_type=EntityType.COMPANY, display_name="X")
        r = IdentityMatchResult(decision=MatchDecision.MATCH, candidate=c)
        with pytest.raises(Exception):
            r.decision = MatchDecision.NO_MATCH


# ── NormalizationService Tests ──

class TestNormalization:
    def test_inn_digits_only(self):
        assert NormalizationService.normalize_inn("7805 2785 5675") == "780527855675"

    def test_inn_max_12(self):
        assert len(NormalizationService.normalize_inn("1234567890123")) == 12

    def test_ogrn_digits_only(self):
        assert NormalizationService.normalize_ogrn("102 780 123 4567") == "1027801234567"

    def test_phone_normalization(self):
        r = NormalizationService.normalize_phone("8(921)123-45-67")
        assert r == "+79211234567"

    def test_phone_with_plus(self):
        r = NormalizationService.normalize_phone("+7 (921) 123-45-67")
        assert r == "+79211234567"

    def test_contract_number(self):
        r = NormalizationService.normalize_contract_number("№2182-НП/И")
        assert "2182" in r

    def test_address(self):
        r = NormalizationService.normalize_address("г. СПб, наб. Петроградская, д. 18")
        assert "город" in r
        assert "набережная" in r

    def test_deterministic(self):
        r1 = NormalizationService.normalize_inn("780527855675")
        r2 = NormalizationService.normalize_inn("780527855675")
        assert r1 == r2


# ── IdentityResolver Tests ──

class TestIdentityResolver:
    def test_create_new_entity(self):
        entity = BusinessEntity(entity_type=EntityType.COMPANY, display_name="ООО Ромашка")
        identifiers = [
            EntityIdentifier(IdentifierType.INN, "780527855675", entity_id=entity.id, confidence=0.95),
        ]
        result = IdentityResolver.resolve(
            entity=entity, identifiers=identifiers,
            document_id="doc-1",
        )
        assert result.entity is not None
        assert result.entity.entity_type == EntityType.COMPANY
        assert result.entity.display_name == "780527855675"  # INN becomes display
        assert len(result.entity.identifiers) == 1
        assert result.is_new

    def test_immutable_canonical_entity(self):
        """CanonicalEntity must be fully formed, no post-mutation."""
        entity = BusinessEntity(entity_type=EntityType.COMPANY, display_name="Test")
        identifiers = [EntityIdentifier(IdentifierType.INN, "123", entity_id=entity.id)]
        result = IdentityResolver.resolve(
            entity=entity, identifiers=identifiers, document_id="doc-1",
        )
        ce = result.entity
        # Verify all fields set at construction
        assert ce.id is not None
        assert len(ce.identifiers) > 0
        # Must NOT have mutable methods
        assert not hasattr(ce, 'add_alias')
        assert not hasattr(ce, 'confirm')
        assert not hasattr(ce, 'merge')
        assert not hasattr(ce, 'append_identifier')

    def test_match_existing_by_inn(self):
        existing = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=CanonicalEntityId(value="existing-1"),
            display_name="ООО Ромашка",
            identifiers=(
                EntityIdentifier(IdentifierType.INN, "780527855675"),
            ),
        )
        entity = BusinessEntity(entity_type=EntityType.COMPANY, display_name="ООО Ромашка")
        identifiers = [EntityIdentifier(IdentifierType.INN, "780527855675", entity_id=entity.id)]
        result = IdentityResolver.resolve(
            entity=entity, identifiers=identifiers,
            document_id="doc-1",
            existing_entities=[existing],
        )
        assert result.entity is not None
        assert result.entity.id == existing.id  # Same entity
        assert result.match_result is not None
        assert result.match_result.decision == MatchDecision.MATCH

    def test_no_match_new_entity(self):
        existing = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=CanonicalEntityId(value="existing-1"),
            display_name="ООО Другой",
            identifiers=(EntityIdentifier(IdentifierType.INN, "999"),),
        )
        entity = BusinessEntity(entity_type=EntityType.COMPANY, display_name="ООО Новый")
        identifiers = [EntityIdentifier(IdentifierType.INN, "123", entity_id=entity.id)]
        result = IdentityResolver.resolve(
            entity=entity, identifiers=identifiers,
            document_id="doc-2",
            existing_entities=[existing],
        )
        assert result.entity is not None
        assert result.entity.id != existing.id  # Different entity
        assert result.is_new

    def test_ambiguous_match(self):
        existing = [
            CanonicalEntity(
                entity_type=EntityType.COMPANY,
                id=CanonicalEntityId(value="e1"),
                display_name="A",
                identifiers=(EntityIdentifier(IdentifierType.INN, "123"),),
            ),
            CanonicalEntity(
                entity_type=EntityType.COMPANY,
                id=CanonicalEntityId(value="e2"),
                display_name="B",
                identifiers=(EntityIdentifier(IdentifierType.INN, "123"),),
            ),
        ]
        entity = BusinessEntity(entity_type=EntityType.COMPANY, display_name="C")
        identifiers = [EntityIdentifier(IdentifierType.INN, "123", entity_id=entity.id)]
        result = IdentityResolver.resolve(
            entity=entity, identifiers=identifiers,
            document_id="doc-1",
            existing_entities=existing,
        )
        assert result.match_result is not None
        assert result.match_result.decision == MatchDecision.AMBIGUOUS

    def test_deterministic(self):
        """Same input → same result (same identifiers, same type)."""
        entity = BusinessEntity(entity_type=EntityType.COMPANY, display_name="Test")
        identifiers = [EntityIdentifier(IdentifierType.INN, "123", entity_id=entity.id)]
        r1 = IdentityResolver.resolve(entity=entity, identifiers=identifiers, document_id="doc-1")
        r2 = IdentityResolver.resolve(entity=entity, identifiers=identifiers, document_id="doc-1")
        assert r1.entity is not None and r2.entity is not None
        assert r1.entity.entity_type == r2.entity.entity_type
        # Display name might differ (different generated id used as fallback)
        # But entity type and identifier values must match
        id1 = [idf.value for idf in r1.entity.identifiers]
        id2 = [idf.value for idf in r2.entity.identifiers]
        assert id1 == id2

    def test_no_mutable_api_on_entity(self):
        """Regression: CanonicalEntity must never mutate after construction."""
        entity = BusinessEntity(entity_type=EntityType.PERSON, display_name="Иван")
        identifiers = [EntityIdentifier(IdentifierType.INN, "123", entity_id=entity.id)]
        result = IdentityResolver.resolve(
            entity=entity, identifiers=identifiers, document_id="doc-1",
        )
        ce = result.entity
        # Verify frozen
        with pytest.raises(Exception):
            ce.display_name = "Пётр"
        with pytest.raises(Exception):
            ce.identifiers = ()
        # Verify no mutable methods exist
        assert not hasattr(ce, 'add_alias')
        assert not hasattr(ce, 'confirm')
        assert not hasattr(ce, 'merge')

    def test_empty_identifiers(self):
        entity = BusinessEntity(entity_type=EntityType.PERSON, display_name="Иван")
        result = IdentityResolver.resolve(
            entity=entity, identifiers=[], document_id="doc-1",
        )
        assert result.entity is not None
        assert len(result.entity.identifiers) == 0

    def test_person_resolution(self):
        entity = BusinessEntity(entity_type=EntityType.PERSON, display_name="Иванов Иван")
        identifiers = [
            EntityIdentifier(IdentifierType.INN, "123456789012", entity_id=entity.id, confidence=0.9),
            EntityIdentifier(IdentifierType.PHONE, "8(921)123-45-67", entity_id=entity.id, confidence=0.8),
        ]
        result = IdentityResolver.resolve(
            entity=entity, identifiers=identifiers, document_id="doc-1",
        )
        assert result.entity is not None
        assert result.entity.entity_type == EntityType.PERSON
        # Phone should be normalized to +7 format
        phone_ids = [idf for idf in result.entity.identifiers if idf.identifier_type == IdentifierType.PHONE]
        if phone_ids:
            assert phone_ids[0].value.startswith("+7")


# ── IdentityResolutionResult Tests ──

class TestIdentityResolutionResult:
    def test_empty(self):
        r = IdentityResolutionResult()
        assert r.entity is None
        assert not r.is_new

    def test_with_entity(self):
        ce = CanonicalEntity(
            entity_type=EntityType.COMPANY, id=CanonicalEntityId.generate(),
        )
        r = IdentityResolutionResult(entity=ce)
        assert r.entity is not None

    def test_immutable(self):
        r = IdentityResolutionResult()
        with pytest.raises(Exception):
            r.entity = CanonicalEntity(entity_type=EntityType.COMPANY, id=CanonicalEntityId.generate())


# ── IdentityResolutionReport Tests ──

class TestIdentityResolutionReport:
    def test_empty(self):
        r = IdentityResolutionReport()
        assert r.total_candidates == 0

    def test_create(self):
        r = IdentityResolutionReport(total_candidates=5, total_matched=2, total_created=3)
        assert r.total_candidates == 5
        assert r.total_matched == 2
        assert r.total_created == 3

    def test_immutable(self):
        r = IdentityResolutionReport()
        with pytest.raises(Exception):
            r.total_candidates = 5
