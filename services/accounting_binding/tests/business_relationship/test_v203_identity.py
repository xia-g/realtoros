"""
Legacy tests — v2.0.3 compatible. Updated for immutable CanonicalEntity.
Old mutable API tests removed. IdentityResolver now tests A3.2 stateless API.
"""
from __future__ import annotations

import pytest

from domain.business_relationship.normalization import NormalizationService
from domain.business_relationship.entity_identifier import EntityIdentifier
from domain.business_relationship.entity import BusinessEntity
from domain.business_relationship.entity_types import EntityType, IdentifierType
from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.fact_types import FactType
from domain.business_relationship.provenance import Provenance, DocumentRevision
from domain.business_relationship.agreement import Agreement
from domain.business_relationship.agreement_id import AgreementId
from domain.business_relationship.knowledge_state import KnowledgeState
from domain.business_relationship.agreement_types import AgreementType as AgType
from domain.business_relationship.entity_alias import EntityAlias as Alias, AliasType
from domain.business_relationship.support_models import (
    MergeCandidate, MergeDecision, ConfidenceHistory, ConfidencePoint,
)
from domain.business_relationship.canonical_entity import CanonicalEntity
from domain.business_relationship.canonical_entity_id import CanonicalEntityId
from domain.business_relationship.canonical_property import CanonicalProperty
from domain.business_relationship.canonical_agreement import CanonicalAgreement
from domain.business_relationship.identity_resolver import IdentityResolver
from domain.business_relationship.identity_candidate import IdentityCandidate
from domain.business_relationship.normalized_identifier import NormalizedIdentifier
from domain.business_relationship.identity_match_result import IdentityMatchResult, MatchDecision
from domain.business_relationship.identity_resolution_result import IdentityResolutionResult, IdentityResolutionReport


# ── Normalization Tests (unchanged) ──

class TestNormalization:
    def test_company_normalization(self):
        n = NormalizationService
        r1 = n.normalize_company("ООО Ромашка")
        r2 = n.normalize_company('ООО "Ромашка"')
        r3 = n.normalize_company("Общество с ограниченной ответственностью Ромашка")
        assert r1 == r2 == r3

    def test_company_ao(self):
        r = NormalizationService.normalize_company("АО «Сбербанк»")
        assert "ао" in r
        assert "сбербанк" in r

    def test_person_normalization(self):
        r = NormalizationService.normalize_person("Иванов Иван Иванович")
        assert r == "иванов иван иванович"

    def test_address_normalization(self):
        r = NormalizationService.normalize_address("г. Санкт-Петербург, наб. Петроградская, д. 18, лит. В")
        assert "город" in r
        assert "набережная" in r
        assert "дом 18" in r
        assert "литера в" in r

    def test_contract_number_normalization(self):
        r = NormalizationService.normalize_contract_number("№2182-НП/И")
        assert r == "2182-НП/И"

    def test_deterministic(self):
        r1 = NormalizationService.normalize_company("ООО Ромашка")
        r2 = NormalizationService.normalize_company("ООО Ромашка")
        assert r1 == r2


# ── CanonicalEntity Tests (immutable) ──

class TestCanonicalEntity:
    def test_create(self):
        ce = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            display_name="ООО Ромашка",
            id=CanonicalEntityId.generate(),
        )
        assert ce.entity_type == EntityType.COMPANY
        assert ce.display_name == "ООО Ромашка"
        assert ce.primary_identifier == ""

    def test_immutable(self):
        ce = CanonicalEntity(entity_type=EntityType.COMPANY, id=CanonicalEntityId.generate())
        with pytest.raises(Exception):
            ce.display_name = "changed"

    def test_with_identifiers(self):
        ei = EntityIdentifier(IdentifierType.INN, "123")
        ce = CanonicalEntity(
            entity_type=EntityType.COMPANY,
            id=CanonicalEntityId.generate(),
            identifiers=(ei,),
        )
        assert ce.primary_identifier == "123"

    def test_property_placeholder(self):
        cp = CanonicalProperty(cadastral_number="78:10:0005522:3018")
        assert cp.cadastral_number == "78:10:0005522:3018"

    def test_no_mutable_api(self):
        ce = CanonicalEntity(entity_type=EntityType.COMPANY, id=CanonicalEntityId.generate())
        assert not hasattr(ce, 'add_alias')
        assert not hasattr(ce, 'confirm')


# ── MergeCandidate Tests (unchanged) ──

class TestMergeCandidate:
    def test_auto_merge(self):
        mc = MergeCandidate("a", "b", similarity_score=99)
        assert mc.decision == MergeDecision.AUTO_MERGE

    def test_review_merge(self):
        mc = MergeCandidate("a", "b", similarity_score=95)
        assert mc.decision == MergeDecision.REVIEW_MERGE

    def test_no_merge(self):
        mc = MergeCandidate("a", "b", similarity_score=50)
        assert mc.decision == MergeDecision.NO_MERGE


# ── ConfidenceHistory Tests (unchanged) ──

class TestConfidenceHistory:
    def test_append_only(self):
        ch = ConfidenceHistory(entity_id="e1")
        assert ch.current_confidence == 0.0
        ch.add("doc-1")
        ch.add("doc-2")
        assert ch.current_confidence > 0.0


# ── IdentityResolver Tests (A3.2 stateless API) ──

class TestIdentityResolver:
    def test_resolve_new_entity(self):
        entity = BusinessEntity(EntityType.COMPANY, "ООО Ромашка")
        identifiers = [EntityIdentifier(IdentifierType.INN, "780527855675", entity_id=entity.id)]
        result = IdentityResolver.resolve(entity=entity, identifiers=identifiers, document_id="doc-1")
        assert result.entity is not None
        assert result.entity.entity_type == EntityType.COMPANY

    def test_same_inn_reuses_entity(self):
        existing = CanonicalEntity(
            entity_type=EntityType.COMPANY, id=CanonicalEntityId.generate(),
            display_name="Ромашка",
            identifiers=(EntityIdentifier(IdentifierType.INN, "780527855675"),),
        )
        entity = BusinessEntity(EntityType.COMPANY, "ООО Ромашка")
        identifiers = [EntityIdentifier(IdentifierType.INN, "780527855675", entity_id=entity.id)]
        result = IdentityResolver.resolve(
            entity=entity, identifiers=identifiers, document_id="doc-1",
            existing_entities=[existing],
        )
        assert result.entity is not None
        assert result.match_result is not None
        assert result.match_result.decision == MatchDecision.MATCH

    def test_property_resolution(self):
        entity = BusinessEntity(EntityType.PROPERTY, "Помещение")
        identifiers = [
            EntityIdentifier(IdentifierType.CADASTRE, "78:10:0005522:3018", entity_id=entity.id),
        ]
        result = IdentityResolver.resolve(
            entity=entity, identifiers=identifiers, document_id="doc-1",
        )
        assert result.entity is not None
        assert result.entity.entity_type == EntityType.PROPERTY
        # CADASTRE should be in identifiers
        cadastres = [idf for idf in result.entity.identifiers if idf.identifier_type == IdentifierType.CADASTRE]
        assert len(cadastres) > 0

    def test_master_data_context(self):
        # MasterDataContext is removed in A3.2 — replaced by IdentityResolutionResult
        entity = BusinessEntity(EntityType.COMPANY, "Тест")
        identifiers = [EntityIdentifier(IdentifierType.INN, "123", entity_id=entity.id)]
        result = IdentityResolver.resolve(entity=entity, identifiers=identifiers, document_id="doc-1")
        assert result.entity is not None
        assert result.candidate is not None

    def test_pipeline_identity_resolution(self):
        """Full pipeline: BusinessEntity → IdentityCandidate → CanonicalEntity."""
        entity = BusinessEntity(EntityType.COMPANY, "ООО Ромашка")
        identifiers = [
            EntityIdentifier(IdentifierType.INN, "780527855675", entity_id=entity.id),
            EntityIdentifier(IdentifierType.PHONE, "+7 (921) 123-45-67", entity_id=entity.id),
        ]
        result = IdentityResolver.resolve(
            entity=entity, identifiers=identifiers, document_id="doc-1",
        )
        assert result.entity is not None
        assert result.candidate is not None
        assert result.match_result is not None
