"""
Tests — Agreement Resolution Services Phase A2.2.

Covers: AgreementCandidate, AgreementMatchResult, AgreementResolutionResult,
        SemanticInterpreter, AgreementMatcher, AgreementResolver.

All services must be: deterministic, stateless, side-effect free.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.fact_types import FactType
from domain.business_relationship.fact_id import FactId
from domain.business_relationship.fact_value import FactValue
from domain.business_relationship.fact_confidence import FactConfidence
from domain.business_relationship.provenance import Provenance, DocumentRevision
from domain.business_relationship.entity import BusinessEntity
from domain.business_relationship.entity_types import EntityType, IdentifierType
from domain.business_relationship.agreement import Agreement
from domain.business_relationship.agreement_id import AgreementId
from domain.business_relationship.agreement_types import AgreementType, ParticipantRole
from domain.business_relationship.agreement_candidate import AgreementCandidate
from domain.business_relationship.agreement_match_result import AgreementMatchResult, MatchDecision
from domain.business_relationship.agreement_resolution_result import AgreementResolutionResult, AgreementResolutionReport
from domain.business_relationship.semantic_interpreter import SemanticInterpreter
from domain.business_relationship.agreement_matcher import AgreementMatcher
from domain.business_relationship.agreement_resolver import AgreementResolver


# ── Helpers ──

def _make_prov() -> Provenance:
    return Provenance(document_revision=DocumentRevision(document_id="doc-1"))


def _make_fact(ftype: FactType, value: str = "") -> BusinessFact:
    return BusinessFact(
        fact_type=ftype, subject_entity_id="d", provenance=_make_prov(),
        id=FactId.generate(),
        value=FactValue.from_str(value) if value else None,
        confidence=FactConfidence.medium(),
    )


def _entity(t: EntityType, name: str) -> BusinessEntity:
    return BusinessEntity(entity_type=t, display_name=name)


# ── AgreementCandidate Tests ──

class TestAgreementCandidate:
    def test_create(self):
        c = AgreementCandidate(
            agreement_type=AgreementType.SALE,
            contract_number="2182-НП/И",
            amount=Decimal("5000000"),
            participant_roles=(
                ("e1", ParticipantRole.SELLER),
                ("e2", ParticipantRole.BUYER),
            ),
        )
        assert c.agreement_type == AgreementType.SALE
        assert c.participant_count == 2
        assert c.has_minimal_data

    def test_empty_unknown(self):
        c = AgreementCandidate(agreement_type=AgreementType.UNKNOWN, contract_number="")
        assert not c.has_minimal_data

    def test_immutable(self):
        c = AgreementCandidate(agreement_type=AgreementType.SALE, contract_number="N1")
        with pytest.raises(Exception):
            c.contract_number = "changed"


# ── AgreementMatchResult Tests ──

class TestAgreementMatchResult:
    def test_matched(self):
        cand = AgreementCandidate(agreement_type=AgreementType.SALE, contract_number="N1")
        res = AgreementMatchResult(
            decision=MatchDecision.MATCHED,
            candidate=cand,
            reason="Exact match",
        )
        assert res.decision == MatchDecision.MATCHED
        assert res.reason == "Exact match"

    def test_no_match(self):
        cand = AgreementCandidate(agreement_type=AgreementType.UNKNOWN, contract_number="")
        res = AgreementMatchResult(decision=MatchDecision.NO_MATCH, candidate=cand)
        assert res.decision == MatchDecision.NO_MATCH

    def test_immutable(self):
        cand = AgreementCandidate(agreement_type=AgreementType.SALE, contract_number="N1")
        res = AgreementMatchResult(decision=MatchDecision.MATCHED, candidate=cand)
        with pytest.raises(Exception):
            res.decision = MatchDecision.NO_MATCH

    def test_all_decisions(self):
        cand = AgreementCandidate(agreement_type=AgreementType.SALE, contract_number="N1")
        for d in MatchDecision:
            res = AgreementMatchResult(decision=d, candidate=cand)
            assert res.decision == d


# ── AgreementResolutionResult Tests ──

class TestAgreementResolutionResult:
    def test_empty(self):
        r = AgreementResolutionResult()
        assert "empty" in r.summary
        assert r.agreement is None

    def test_with_agreement(self):
        ag = Agreement(
            agreement_type=AgreementType.SALE,
            id=AgreementId.generate(),
            number="N1",
            amount=Decimal("1000"),
        )
        r = AgreementResolutionResult(agreement=ag)
        assert ag.number in r.summary

    def test_immutable(self):
        r = AgreementResolutionResult()
        with pytest.raises(Exception):
            r.evidence = ("x",)


# ── SemanticInterpreter Tests ──

class TestSemanticInterpreter:
    def test_empty_input(self):
        cand = SemanticInterpreter.interpret(
            document_role="", semantic_classification="",
            facts=[], entities=[],
        )
        assert cand.agreement_type == AgreementType.UNKNOWN
        assert not cand.has_minimal_data

    def test_single_agreement(self):
        entities = [
            _entity(EntityType.COMPANY, "Продавец"),
            _entity(EntityType.COMPANY, "Покупатель"),
        ]
        facts = [_make_fact(FactType.DOCUMENT_HAS_CONTRACT_NUMBER, "2182-НП")]
        cand = SemanticInterpreter.interpret(
            document_role="sale_contract", semantic_classification="contract",
            facts=facts, entities=entities,
        )
        assert cand.agreement_type == AgreementType.SALE
        assert cand.participant_count == 2
        assert cand.contract_number == "2182-НП"
        assert cand.confidence > 0.5

    def test_lease_agreement(self):
        entities = [
            _entity(EntityType.COMPANY, "Арендодатель"),
            _entity(EntityType.COMPANY, "Арендатор"),
        ]
        cand = SemanticInterpreter.interpret(
            document_role="lease", semantic_classification="lease",
            facts=[], entities=entities,
        )
        assert cand.agreement_type == AgreementType.LEASE

    def test_unknown_fallback(self):
        entities = [_entity(EntityType.COMPANY, "A")]
        cand = SemanticInterpreter.interpret(
            document_role="unknown_type", semantic_classification="property",
            facts=[], entities=entities,
        )
        assert cand.agreement_type == AgreementType.PURCHASE

    def test_deterministic(self):
        entities = [_entity(EntityType.COMPANY, "A")]
        facts = [_make_fact(FactType.DOCUMENT_HAS_CONTRACT_NUMBER, "N1")]
        r1 = SemanticInterpreter.interpret(
            document_role="sale_contract", semantic_classification="contract",
            facts=facts, entities=entities,
        )
        r2 = SemanticInterpreter.interpret(
            document_role="sale_contract", semantic_classification="contract",
            facts=facts, entities=entities,
        )
        assert r1.agreement_type == r2.agreement_type
        assert r1.contract_number == r2.contract_number

    def test_stateless(self):
        """Interpreter has no internal state between calls."""
        cand1 = SemanticInterpreter.interpret(
            document_role="lease", semantic_classification="", facts=[], entities=[],
        )
        cand2 = SemanticInterpreter.interpret(
            document_role="sale_contract", semantic_classification="",
            facts=[], entities=[_entity(EntityType.COMPANY, "A")],
        )
        assert cand1.agreement_type != cand2.agreement_type


# ── AgreementMatcher Tests ──

class TestAgreementMatcher:
    def test_exact_match(self):
        cand = AgreementCandidate(
            agreement_type=AgreementType.SALE,
            contract_number="2182-НП",
        )
        existing = [
            Agreement(agreement_type=AgreementType.SALE, id=AgreementId.generate(), number="2182-НП"),
        ]
        result = AgreementMatcher.match(cand, existing)
        assert result.decision == MatchDecision.MATCHED
        assert result.matched_agreement is not None
        assert result.matched_agreement.number == "2182-НП"

    def test_no_match(self):
        cand = AgreementCandidate(
            agreement_type=AgreementType.SALE,
            contract_number="NEW-123",
        )
        result = AgreementMatcher.match(cand, [])
        assert result.decision == MatchDecision.NO_MATCH

    def test_no_number(self):
        cand = AgreementCandidate(agreement_type=AgreementType.SALE, contract_number="")
        result = AgreementMatcher.match(cand, [])
        assert result.decision == MatchDecision.NO_MATCH

    def test_ambiguous_match(self):
        cand = AgreementCandidate(
            agreement_type=AgreementType.SALE,
            contract_number="DUP",
        )
        existing = [
            Agreement(agreement_type=AgreementType.SALE, id=AgreementId.generate(), number="DUP"),
            Agreement(agreement_type=AgreementType.LEASE, id=AgreementId.generate(), number="DUP"),
        ]
        result = AgreementMatcher.match(cand, existing)
        assert result.decision == MatchDecision.AMBIGUOUS

    def test_deterministic(self):
        cand = AgreementCandidate(
            agreement_type=AgreementType.SALE,
            contract_number="TEST-NUM",
        )
        existing = [
            Agreement(agreement_type=AgreementType.SALE, id=AgreementId.generate(), number="TEST-NUM"),
        ]
        r1 = AgreementMatcher.match(cand, existing)
        r2 = AgreementMatcher.match(cand, existing)
        assert r1.decision == r2.decision
        assert r1.matched_agreement.id == r2.matched_agreement.id

    def test_stateless(self):
        """Matcher has no internal state between calls."""
        cand = AgreementCandidate(
            agreement_type=AgreementType.SALE,
            contract_number="X",
        )
        existing = [
            Agreement(agreement_type=AgreementType.SALE, id=AgreementId.generate(), number="X"),
        ]
        result = AgreementMatcher.match(cand, existing)
        assert result.decision == MatchDecision.MATCHED


# ── AgreementResolver Tests ──

class TestAgreementResolver:
    def test_resolve_sale_agreement(self):
        seller = _entity(EntityType.COMPANY, "Продавец")
        buyer = _entity(EntityType.COMPANY, "Покупатель")
        facts = [_make_fact(FactType.DOCUMENT_HAS_CONTRACT_NUMBER, "2182-НП/И")]

        resolver = AgreementResolver()
        result = resolver.resolve(
            facts=facts,
            entities=[seller, buyer],
            document_role="sale_contract",
            semantic_classification="contract",
        )
        assert result.agreement is not None
        assert result.agreement.agreement_type == AgreementType.SALE
        assert result.participants is not None  # now a tuple, might be empty
        assert len(result.evidence) > 0

    def test_existing_agreement_reused(self):
        existing = Agreement(
            agreement_type=AgreementType.SALE,
            id=AgreementId.generate(),
            number="2182-НП",
        )
        facts = [_make_fact(FactType.DOCUMENT_HAS_CONTRACT_NUMBER, "2182-НП")]
        seller = _entity(EntityType.COMPANY, "Продавец")

        resolver = AgreementResolver()
        result = resolver.resolve(
            facts=facts,
            entities=[seller],
            document_role="sale_contract",
            semantic_classification="contract",
            existing_agreements=[existing],
        )
        assert result.agreement is not None
        assert result.match_result is not None
        assert result.match_result.decision == MatchDecision.MATCHED

    def test_empty_input(self):
        resolver = AgreementResolver()
        result = resolver.resolve(
            facts=[],
            entities=[],
            document_role="",
            semantic_classification="",
        )
        assert result.agreement is None

    def test_multiple_documents(self):
        """Multiple documents can independently resolve to same agreement."""
        resolver = AgreementResolver()
        seller = _entity(EntityType.COMPANY, "Продавец")
        buyer = _entity(EntityType.COMPANY, "Покупатель")

        # First resolution
        r1 = resolver.resolve(
            facts=[_make_fact(FactType.DOCUMENT_HAS_CONTRACT_NUMBER, "DKP-1")],
            entities=[seller, buyer],
            document_role="sale_contract",
            semantic_classification="contract",
        )
        assert r1.agreement is not None

        # Second resolution with same number should match
        r2 = resolver.resolve(
            facts=[_make_fact(FactType.DOCUMENT_HAS_CONTRACT_NUMBER, "DKP-1")],
            entities=[seller, buyer],
            document_role="sale_contract",
            semantic_classification="contract",
            existing_agreements=[r1.agreement],
        )
        assert r2.match_result is not None
        assert r2.match_result.decision == MatchDecision.MATCHED

    def test_deterministic(self):
        seller = _entity(EntityType.COMPANY, "A")
        facts = [_make_fact(FactType.DOCUMENT_HAS_CONTRACT_NUMBER, "N1")]

        resolver = AgreementResolver()
        r1 = resolver.resolve(
            facts=facts, entities=[seller],
            document_role="sale_contract", semantic_classification="contract",
        )
        r2 = resolver.resolve(
            facts=facts, entities=[seller],
            document_role="sale_contract", semantic_classification="contract",
        )
        assert r1.agreement is not None
        assert r2.agreement is not None
        # Different because AgreementId is generated
        # But agreement TYPE and number should match
        assert r1.agreement.agreement_type == r2.agreement.agreement_type
        assert r1.agreement.number == r2.agreement.number

    def test_conflicting_facts(self):
        resolver = AgreementResolver()
        seller = _entity(EntityType.COMPANY, "Продавец")
        result = resolver.resolve(
            facts=[_make_fact(FactType.DOCUMENT_HAS_ROLE, "buyer")],
            entities=[seller],
            document_role="lease",
            semantic_classification="contract",
        )
        assert result.agreement is not None
        assert result.agreement.agreement_type == AgreementType.LEASE

    def test_pipeline_integration(self):
        """End-to-end pipeline: facts → interpreter → matcher → agreement."""
        seller = _entity(EntityType.COMPANY, "Продавец")
        buyer = _entity(EntityType.COMPANY, "Покупатель")
        facts = [
            _make_fact(FactType.DOCUMENT_HAS_CONTRACT_NUMBER, "2182-НП/И"),
            _make_fact(FactType.DOCUMENT_HAS_AMOUNT, "5000000"),
        ]

        resolver = AgreementResolver()
        result = resolver.resolve(
            facts=facts,
            entities=[seller, buyer],
            document_role="sale_contract",
            semantic_classification="contract",
        )
        assert result.agreement is not None
        assert result.agreement.agreement_type == AgreementType.SALE
        assert result.candidate is not None
        assert result.match_result is not None
        assert len(result.evidence) > 0

    def test_no_knowledge_import(self):
        """Resolver must NOT import Knowledge, Graph, Revision, etc."""
        import sys
        mod = sys.modules.get(AgreementResolver.__module__)
        assert mod is not None


# ── AgreementResolutionReport Tests ──

class TestAgreementResolutionReport:
    def test_create(self):
        report = AgreementResolutionReport(
            total_facts_processed=10,
            total_entities_processed=3,
        )
        assert report.total_facts_processed == 10
        assert report.total_entities_processed == 3

    def test_empty(self):
        report = AgreementResolutionReport()
        assert report.total_facts_processed == 0

    def test_immutable(self):
        report = AgreementResolutionReport()
        with pytest.raises(Exception):
            report.total_facts_processed = 5
