"""
Tests — Business Relationship Engine v2.0.2
Agreement Resolution & Business Semantics
"""
from __future__ import annotations

import pytest

from domain.business_relationship.entity import BusinessEntity
from domain.business_relationship.entity_types import EntityType, IdentifierType
from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.fact_types import FactType
from domain.business_relationship.provenance import Provenance, DocumentRevision
from domain.business_relationship.document_reference import DocumentReference, ReferenceType
from domain.business_relationship.agreement_types import AgreementType, ParticipantRole
from domain.business_relationship.agreement import Agreement
from domain.business_relationship.agreement_participant import AgreementParticipant
from domain.business_relationship.semantic_interpreter import SemanticInterpreter, SemanticInterpretation
from domain.business_relationship.agreement_matcher import AgreementMatcher
from domain.business_relationship.agreement_resolver import AgreementResolver, AgreementContext


# ── Fixtures ──

def _make_prov():
    return Provenance(document_revision=DocumentRevision(document_id="doc-1"))

def _make_fact(ftype: FactType, value: str = "", **kw) -> BusinessFact:
    return BusinessFact(fact_type=ftype, subject_entity_id="d", provenance=_make_prov(), value=value, **kw)

def _entity(t: EntityType, name: str, eid: str | None = None) -> BusinessEntity:
    e = BusinessEntity(entity_type=t, display_name=name)
    if eid: e.id = eid
    return e


# ── SemanticInterpreter Tests ──

class TestSemanticInterpreter:
    def test_sale_agreement(self):
        interp = SemanticInterpreter().interpret(
            document_role="sale_contract", semantic_classification="contract",
            facts=[], entities=[_entity(EntityType.COMPANY, "Продавец")]
        )
        assert interp.agreement_type == AgreementType.SALE

    def test_lease_agreement(self):
        interp = SemanticInterpreter().interpret(
            document_role="lease", semantic_classification="contract",
            facts=[], entities=[]
        )
        assert interp.agreement_type == AgreementType.LEASE

    def test_service_agreement(self):
        interp = SemanticInterpreter().interpret(
            document_role="service", semantic_classification="contract",
            facts=[], entities=[]
        )
        assert interp.agreement_type == AgreementType.SERVICE

    def test_agency_agreement(self):
        interp = SemanticInterpreter().interpret(
            document_role="agency", semantic_classification="contract",
            facts=[], entities=[]
        )
        assert interp.agreement_type == AgreementType.AGENCY

    def test_commission_agreement(self):
        interp = SemanticInterpreter().interpret(
            document_role="commission", semantic_classification="contract",
            facts=[], entities=[]
        )
        assert interp.agreement_type == AgreementType.COMMISSION

    def test_framework_agreement(self):
        interp = SemanticInterpreter().interpret(
            document_role="amendment", semantic_classification="contract",
            facts=[], entities=[]
        )
        assert interp.agreement_type == AgreementType.FRAMEWORK

    def test_offer_agreement(self):
        interp = SemanticInterpreter().interpret(
            document_role="invoice", semantic_classification="invoice",
            facts=[], entities=[]
        )
        assert interp.agreement_type == AgreementType.OFFER

    def test_unknown_fallback(self):
        interp = SemanticInterpreter().interpret(
            document_role="unknown", semantic_classification="unknown",
            facts=[], entities=[]
        )
        assert interp.agreement_type == AgreementType.UNKNOWN

    def test_participant_roles_sale(self):
        seller = _entity(EntityType.COMPANY, "Продавец")
        buyer = _entity(EntityType.COMPANY, "Покупатель")
        interp = SemanticInterpreter().interpret(
            document_role="sale_contract", semantic_classification="contract",
            facts=[], entities=[seller, buyer]
        )
        assert any(r == ParticipantRole.SELLER for _, r in interp.participant_roles)
        assert any(r == ParticipantRole.BUYER for _, r in interp.participant_roles)

    def test_participant_roles_lease(self):
        ll = _entity(EntityType.COMPANY, "Арендодатель")
        tn = _entity(EntityType.COMPANY, "Арендатор")
        interp = SemanticInterpreter().interpret(
            document_role="lease", semantic_classification="contract",
            facts=[], entities=[ll, tn]
        )
        assert any(r == ParticipantRole.LANDLORD for _, r in interp.participant_roles)
        assert any(r == ParticipantRole.TENANT for _, r in interp.participant_roles)


# ── AgreementMatcher Tests ──

class TestAgreementMatcher:
    def test_find_by_number(self):
        a = Agreement(AgreementType.SALE, number="2182-НП/И")
        m = AgreementMatcher([a])
        assert m.find_by_number("2182-НП/И") is not None
        assert m.find_by_number("9999") is None

    def test_document_reference_match(self):
        a = Agreement(AgreementType.SALE, number="2182-НП/И")
        m = AgreementMatcher([a])
        ref = DocumentReference(ReferenceType.ACT_FOR, "akt-1", "2182-НП/И", provenance=_make_prov())
        found = m.find_or_none(document_references=[ref])
        assert found is not None
        assert found.number == "2182-НП/И"

    def test_new_agreement_returned_none(self):
        m = AgreementMatcher()
        found = m.find_or_none(number="12345")
        assert found is None


# ── AgreementResolver Tests ──

class TestAgreementResolver:
    def test_resolve_sale_agreement(self):
        seller = _entity(EntityType.COMPANY, "Продавец")
        buyer = _entity(EntityType.COMPANY, "Покупатель")
        facts = [_make_fact(FactType.DOCUMENT_HAS_CONTRACT_NUMBER, "2182-НП")]
        resolver = AgreementResolver()
        ctx = resolver.resolve(
            document_role="sale_contract", semantic_type="contract",
            facts=facts, entities=[seller, buyer],
            document_id="doc-1",
        )
        assert ctx.agreement is not None
        assert ctx.agreement.agreement_type == AgreementType.SALE
        assert len(ctx.participants) == 2

    def test_existing_agreement_reused(self):
        a = Agreement(AgreementType.SALE, number="2182-НП")
        m = AgreementMatcher([a])
        resolver = AgreementResolver(matcher=m)
        ctx = resolver.resolve(
            document_role="sale_contract", semantic_type="contract",
            facts=[_make_fact(FactType.DOCUMENT_HAS_CONTRACT_NUMBER, "2182-НП")],
            entities=[], document_id="doc-2",
        )
        assert ctx.agreement is not None
        assert ctx.agreement.id == a.id  # reused

    def test_agreement_context_has_evidence(self):
        resolver = AgreementResolver()
        ctx = resolver.resolve(
            document_role="lease", semantic_type="contract",
            facts=[], entities=[_entity(EntityType.COMPANY, "A"), _entity(EntityType.COMPANY, "B")],
            document_id="d",
        )
        assert len(ctx.resolution_evidence) > 0

    def test_pipeline_integration(self):
        """Full pipeline: entities → facts → references → agreement."""
        seller = _entity(EntityType.COMPANY, "Шульгина")
        buyer = _entity(EntityType.COMPANY, "Комитет")
        prop = _entity(EntityType.PROPERTY, "78:10:0005522:3018")

        facts = [
            _make_fact(FactType.DOCUMENT_HAS_PARTY),
            _make_fact(FactType.DOCUMENT_HAS_PROPERTY),
            _make_fact(FactType.DOCUMENT_HAS_AMOUNT, "5000000"),
            _make_fact(FactType.DOCUMENT_HAS_CONTRACT_NUMBER, "2182-НП/И"),
        ]
        refs = [DocumentReference(ReferenceType.REFERS_TO, "doc-1", "2182-НП/И", provenance=_make_prov())]

        resolver = AgreementResolver()
        ctx = resolver.resolve(
            document_role="sale_contract", semantic_type="contract",
            facts=facts, entities=[seller, buyer, prop],
            document_id="doc-1", document_references=refs,
        )
        assert ctx.agreement is not None
        assert ctx.agreement.agreement_type == AgreementType.SALE
        assert ctx.agreement.number == "2182-НП/И"
        assert ctx.agreement.amount > 0
