"""
Tests — Business Relationship Engine v2.0.3
Master Data Resolution & Canonical Identity
"""
from __future__ import annotations

import pytest

from domain.business_relationship.normalization import NormalizationService
from domain.business_relationship.entity import BusinessEntity, EntityIdentifier
from domain.business_relationship.entity_types import EntityType, IdentifierType
from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.fact_types import FactType
from domain.business_relationship.provenance import Provenance, DocumentRevision
from domain.business_relationship.agreement import Agreement
from domain.business_relationship.agreement_id import AgreementId
from domain.business_relationship.knowledge_state import KnowledgeState
from domain.business_relationship.agreement_types import AgreementType
from domain.business_relationship.support_models import (
    Alias, AliasType, MergeCandidate, MergeDecision, ConfidenceHistory, ConfidencePoint,
)
from domain.business_relationship.canonical_entity import (
    CanonicalEntity, CanonicalProperty, CanonicalAgreement,
)
from domain.business_relationship.identity_resolver import IdentityResolver, MasterDataContext


# ── Normalization Tests ──

class TestNormalization:
    def test_company_normalization(self):
        n = NormalizationService
        r1 = n.normalize_company("ООО Ромашка")
        r2 = n.normalize_company('ООО "Ромашка"')
        r3 = n.normalize_company("Общество с ограниченной ответственностью Ромашка")
        assert r1 == r2 == r3

    def test_company_ao(self):
        n = NormalizationService
        r = n.normalize_company("АО «Сбербанк»")
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

    def test_phone_normalization(self):
        r = NormalizationService.normalize_phone("8 (921) 123-45-67")
        assert r == "+79211234567"

    def test_email_normalization(self):
        r = NormalizationService.normalize_email("TESt@Example.COM")
        assert r == "test@example.com"

    def test_cadastre_normalization(self):
        r = NormalizationService.normalize_cadastre("78 : 10 : 0005522 : 3018")
        assert r == "78:10:0005522:3018"


# ── Canonical Entity Tests ──

class TestCanonicalEntity:
    def test_create(self):
        ce = CanonicalEntity(EntityType.COMPANY, display_name="ООО Ромашка")
        assert ce.entity_type == EntityType.COMPANY

    def test_add_alias(self):
        ce = CanonicalEntity(EntityType.COMPANY, display_name="ООО Ромашка")
        ce.add_alias("ООО «Ромашка»", "ооо ромашка")
        assert len(ce.aliases) == 1

    def test_confidence_increases(self):
        ce = CanonicalEntity(EntityType.COMPANY, display_name="Test")
        ce.confirm("doc-1")
        assert ce.confidence > 0
        ce.confirm("doc-2")
        assert ce.confidence >= 0.2

    def test_property_confidence(self):
        cp = CanonicalProperty(cadastral_number="78:10:0005522:3018")
        cp.confirm("doc-1")
        cp.confirm("doc-2")
        cp.confirm("doc-3")
        assert cp.confidence >= 0.3
        assert cp.confidence_history is not None
        assert cp.confidence_history.confirmation_count == 3


# ── Merge Candidate Tests ──

class TestMergeCandidate:
    def test_auto_merge(self):
        mc = MergeCandidate(left_entity_id="a", right_entity_id="b", similarity_score=99)
        assert mc.decision == MergeDecision.AUTO_MERGE

    def test_review_merge(self):
        mc = MergeCandidate(left_entity_id="a", right_entity_id="b", similarity_score=96)
        assert mc.decision == MergeDecision.REVIEW_MERGE

    def test_no_merge(self):
        mc = MergeCandidate(left_entity_id="a", right_entity_id="b", similarity_score=80)
        assert mc.decision == MergeDecision.NO_MERGE


# ── Confidence History Tests ──

class TestConfidenceHistory:
    def test_append_only(self):
        ch = ConfidenceHistory(entity_id="e-1", initial_confidence=0.3)
        ch.add("doc-1")
        ch.add("doc-2")
        assert ch.confirmation_count == 2
        assert ch.current_confidence == 0.5


# ── Identity Resolver Tests ──

class TestIdentityResolver:
    def _make_prov(self):
        return Provenance(document_revision=DocumentRevision(document_id="d"))

    def test_resolve_new_entity(self):
        resolver = IdentityResolver()
        e = BusinessEntity(EntityType.COMPANY, "ООО Тест")
        idf = EntityIdentifier(IdentifierType.INN, "123456789012", e.id)
        ctx = resolver.resolve(
            entities=[e], identifiers=[idf], agreement=None, facts=[], document_id="d-1",
        )
        assert len(ctx.canonical_entities) == 1
        assert ctx.canonical_entities[0].confidence > 0

    def test_same_inn_reuses_entity(self):
        resolver = IdentityResolver()
        e1 = BusinessEntity(EntityType.COMPANY, "ООО Тест")
        idf1 = EntityIdentifier(IdentifierType.INN, "123456789012", e1.id)
        resolver.resolve(entities=[e1], identifiers=[idf1], agreement=None, facts=[], document_id="d-1")

        # Same INN, different display name
        e2 = BusinessEntity(EntityType.COMPANY, 'ООО "Тест"')
        idf2 = EntityIdentifier(IdentifierType.INN, "123456789012", e2.id)
        ctx2 = resolver.resolve(entities=[e2], identifiers=[idf2], agreement=None, facts=[], document_id="d-2")

        assert len(ctx2.canonical_entities) == 1
        assert ctx2.canonical_entities[0].confidence > 0.1  # increased

    def test_property_resolution(self):
        resolver = IdentityResolver()
        prop_entity = BusinessEntity(EntityType.PROPERTY, "78:10:0005522:3018")
        idf = EntityIdentifier(IdentifierType.CADASTRE, "78:10:0005522:3018", prop_entity.id)
        ctx = resolver.resolve(
            entities=[prop_entity], identifiers=[idf], agreement=None, facts=[], document_id="d-1",
        )
        assert len(ctx.canonical_properties) >= 1

    def test_agreement_resolution(self):
        resolver = IdentityResolver()
        ag = Agreement(agreement_type=AgreementType.SALE, number="2182-НП/И", id=AgreementId.generate())
        ctx = resolver.resolve(
            entities=[], identifiers=[], agreement=ag, facts=[], document_id="d-1",
        )
        assert len(ctx.canonical_agreements) >= 1

    def test_master_data_context(self):
        ctx = MasterDataContext(
            canonical_entities=[CanonicalEntity(EntityType.COMPANY, "X")],
            canonical_properties=[CanonicalProperty(cadastral_number="78:10:1")],
            canonical_agreements=[CanonicalAgreement(number="N1")],
            merge_candidates=[MergeCandidate("a", "b", 99)],
        )
        assert "entities=1" in ctx.summary
        assert "agreements=1" in ctx.summary

    def test_pipeline_identity_resolution(self):
        """Full identity resolution from entities + agreement."""
        resolver = IdentityResolver()

        seller = BusinessEntity(EntityType.COMPANY, "ИП Шульгина")
        buyer = BusinessEntity(EntityType.COMPANY, "Комитет имущественных отношений")
        prop = BusinessEntity(EntityType.PROPERTY, "78:10:0005522:3018")

        inn_seller = EntityIdentifier(IdentifierType.INN, "780527855675", seller.id, confidence=0.95)
        inn_buyer = EntityIdentifier(IdentifierType.INN, "7840066803", buyer.id, confidence=0.90)
        cadastre = EntityIdentifier(IdentifierType.CADASTRE, "78:10:0005522:3018", prop.id, confidence=0.95)

        ag = Agreement(agreement_type=AgreementType.SALE, number="2182-НП/И", id=AgreementId.generate())

        ctx = resolver.resolve(
            entities=[seller, buyer, prop],
            identifiers=[inn_seller, inn_buyer, cadastre],
            agreement=ag,
            facts=[], document_id="doc-1",
        )

        assert len(ctx.canonical_entities) >= 2  # seller + buyer
        assert len(ctx.canonical_properties) >= 1
        assert len(ctx.canonical_agreements) >= 1
        assert "MasterData" in ctx.summary
