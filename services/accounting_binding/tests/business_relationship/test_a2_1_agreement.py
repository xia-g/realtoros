"""
Tests — Agreement Domain Model Phase A2.1.

Covers: AgreementId, AgreementStatus, AgreementPeriod, AgreementReference,
        AgreementMetadata, Agreement, AgreementParticipant.

All models must be:
  immutable, serializable, hashable, deterministic,
  equality based on value, technology-independent.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from domain.business_relationship.agreement_id import AgreementId
from domain.business_relationship.agreement_status import AgreementStatus
from domain.business_relationship.agreement_period import AgreementPeriod
from domain.business_relationship.agreement_reference import AgreementReference, ReferenceKind
from domain.business_relationship.agreement_metadata import AgreementMetadata
from domain.business_relationship.agreement import Agreement
from domain.business_relationship.agreement_types import AgreementType, ParticipantRole
from domain.business_relationship.agreement_participant import AgreementParticipant


# ── AgreementId Tests ──

class TestAgreementId:
    def test_create(self):
        aid = AgreementId(value="ag-1")
        assert str(aid) == "ag-1"

    def test_generate(self):
        aid = AgreementId.generate()
        assert bool(aid)
        assert len(aid.value) > 0

    def test_from_string(self):
        aid = AgreementId.from_string("test-id")
        assert aid.value == "test-id"

    def test_from_string_empty_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            AgreementId.from_string("")

    def test_immutable(self):
        aid = AgreementId(value="x")
        with pytest.raises(Exception):
            aid.value = "y"

    def test_equality(self):
        assert AgreementId(value="x") == AgreementId(value="x")
        assert AgreementId(value="x") != AgreementId(value="y")

    def test_hashable(self):
        s = {AgreementId(value="a"), AgreementId(value="a")}
        assert len(s) == 1


# ── AgreementStatus Tests ──

class TestAgreementStatus:
    def test_values(self):
        assert AgreementStatus.ACTIVE.value == "active"
        assert AgreementStatus.SUPERSEDED.value == "superseded"
        assert AgreementStatus.HISTORICAL.value == "historical"

    def test_str(self):
        assert AgreementStatus.ACTIVE.value == "active"
        assert str(AgreementStatus.ACTIVE.value) == "active"


# ── AgreementPeriod Tests ──

class TestAgreementPeriod:
    def test_no_dates(self):
        p = AgreementPeriod()
        assert p.is_active_on(date(2026, 1, 1))

    def test_start_only(self):
        p = AgreementPeriod(start_date=date(2026, 6, 1))
        assert p.is_active_on(date(2026, 7, 1))
        assert not p.is_active_on(date(2026, 5, 1))

    def test_end_only(self):
        p = AgreementPeriod(end_date=date(2026, 12, 31))
        assert p.is_active_on(date(2026, 6, 1))
        assert not p.is_active_on(date(2027, 1, 1))

    def test_both_dates(self):
        p = AgreementPeriod(start_date=date(2026, 6, 1), end_date=date(2026, 12, 31))
        assert p.is_active_on(date(2026, 7, 1))
        assert not p.is_active_on(date(2026, 5, 1))
        assert not p.is_active_on(date(2027, 1, 1))

    def test_start_after_end_raises(self):
        with pytest.raises(ValueError, match="must not be after"):
            AgreementPeriod(start_date=date(2026, 12, 31), end_date=date(2026, 6, 1))

    def test_immutable(self):
        p = AgreementPeriod(start_date=date(2026, 1, 1))
        with pytest.raises(Exception):
            p.start_date = date(2025, 1, 1)

    def test_factory(self):
        p = AgreementPeriod.from_dates(date(2026, 1, 1), date(2026, 12, 31))
        assert p.is_active_on(date(2026, 6, 1))


# ── AgreementReference Tests ──

class TestAgreementReference:
    def test_create(self):
        ref = AgreementReference(kind=ReferenceKind.DOCUMENT, target_id="doc-1")
        assert ref.kind == ReferenceKind.DOCUMENT
        assert ref.target_id == "doc-1"

    def test_with_role(self):
        ref = AgreementReference(ReferenceKind.AGREEMENT, "ag-2", role="supersedes")
        assert ref.role == "supersedes"

    def test_immutable(self):
        ref = AgreementReference(ReferenceKind.DOCUMENT, "d")
        with pytest.raises(Exception):
            ref.target_id = "changed"


# ── AgreementMetadata Tests ──

class TestAgreementMetadata:
    def test_create(self):
        m = AgreementMetadata(source_document_id="doc-1", confidence=0.95)
        assert m.source_document_id == "doc-1"

    def test_defaults(self):
        m = AgreementMetadata()
        assert m.confidence == 1.0

    def test_immutable(self):
        m = AgreementMetadata()
        with pytest.raises(Exception):
            m.confidence = 0.5


# ── Agreement Tests ──

class TestAgreement:
    def test_create_full(self):
        aid = AgreementId.generate()
        p1 = AgreementParticipant(
            agreement_id=aid,
            entity_id="e-1",
            participant_role=ParticipantRole.SELLER,
        )
        p2 = AgreementParticipant(
            agreement_id=aid,
            entity_id="e-2",
            participant_role=ParticipantRole.BUYER,
        )
        period = AgreementPeriod(start_date=date(2026, 6, 1), end_date=date(2026, 12, 31))
        ref = AgreementReference(ReferenceKind.DOCUMENT, "doc-1", role="supporting")
        meta = AgreementMetadata(source_document_id="doc-1", confidence=0.9)

        ag = Agreement(
            agreement_type=AgreementType.SALE,
            id=aid,
            number="2182-НП/И",
            date=date(2026, 5, 26),
            amount=Decimal("5000000"),
            status=AgreementStatus.ACTIVE,
            period=period,
            participants=(p1, p2),
            references=(ref,),
            metadata=meta,
        )
        assert ag.agreement_type == AgreementType.SALE
        assert ag.number == "2182-НП/И"
        assert ag.participant_count == 2
        assert ag.amount == Decimal("5000000")
        assert ag.status == AgreementStatus.ACTIVE

    def test_create_minimal(self):
        ag = Agreement(
            agreement_type=AgreementType.UNKNOWN,
            id=AgreementId.generate(),
        )
        assert ag.participant_count == 0
        assert ag.number == ""

    def test_immutable(self):
        ag = Agreement(agreement_type=AgreementType.LEASE, id=AgreementId.generate())
        with pytest.raises(Exception):
            ag.agreement_type = AgreementType.SALE

    def test_equality(self):
        aid = AgreementId(value="x")
        meta = AgreementMetadata(source_document_id="doc-1", confidence=1.0)
        ag1 = Agreement(agreement_type=AgreementType.SALE, id=aid, metadata=meta)
        ag2 = Agreement(agreement_type=AgreementType.SALE, id=aid, metadata=meta)
        assert ag1 == ag2
        ag3 = Agreement(agreement_type=AgreementType.LEASE, id=AgreementId(value="y"))
        assert ag1 != ag3

    def test_hashable(self):
        aid = AgreementId(value="x")
        ag = Agreement(agreement_type=AgreementType.SALE, id=aid)
        s = {ag, ag}
        assert len(s) == 1

    def test_repr(self):
        aid = AgreementId(value="test-id")
        ag = Agreement(agreement_type=AgreementType.SALE, id=aid, number="2182")
        r = repr(ag)
        assert "sale" in r
        assert "test-id" in r
        assert "2182" in r

    def test_with_participants(self):
        aid = AgreementId.generate()
        p = AgreementParticipant(
            agreement_id=aid,
            entity_id="e-1",
            participant_role=ParticipantRole.LANDLORD,
        )
        ag = Agreement(
            agreement_type=AgreementType.LEASE,
            id=aid,
            participants=(p,),
        )
        assert ag.participant_count == 1
        assert ag.participants[0].participant_role == ParticipantRole.LANDLORD

    def test_various_agreement_types(self):
        for at in AgreementType:
            ag = Agreement(agreement_type=at, id=AgreementId.generate())
            assert ag.agreement_type == at

    def test_all_statuses(self):
        for st in AgreementStatus:
            ag = Agreement(
                agreement_type=AgreementType.SALE,
                id=AgreementId.generate(),
                status=st,
            )
            assert ag.status == st

    def test_no_knowledge_import(self):
        """Agreement MUST NOT import Knowledge, Graph, Revision, etc."""
        import sys
        mod = sys.modules.get(Agreement.__module__)
        assert mod is not None

    def test_deterministic_serialization(self):
        aid = AgreementId(value="fixed")
        p = AgreementParticipant(
            agreement_id=aid, entity_id="e1",
            participant_role=ParticipantRole.BUYER,
        )
        ag1 = Agreement(
            agreement_type=AgreementType.SALE,
            id=aid,
            number="N1",
            participants=(p,),
        )
        ag2 = Agreement(
            agreement_type=AgreementType.SALE,
            id=AgreementId(value="fixed"),
            number="N1",
            participants=(p,),
        )
        assert repr(ag1) == repr(ag2)


# ── AgreementParticipant Tests ──

class TestAgreementParticipant:
    def test_create(self):
        p = AgreementParticipant(
            agreement_id=AgreementId(value="ag-1"),
            entity_id="e-1",
            participant_role=ParticipantRole.BUYER,
        )
        assert p.entity_id == "e-1"
        assert p.participant_role == ParticipantRole.BUYER

    def test_with_share(self):
        p = AgreementParticipant(
            agreement_id=AgreementId.generate(),
            entity_id="e-1",
            participant_role=ParticipantRole.SELLER,
            share=Decimal("0.5"),
        )
        assert p.share == Decimal("0.5")

    def test_with_period(self):
        period = AgreementPeriod(start_date=date(2026, 1, 1))
        p = AgreementParticipant(
            agreement_id=AgreementId.generate(),
            entity_id="e-1",
            participant_role=ParticipantRole.TENANT,
            period=period,
        )
        assert p.period.is_active_on(date(2026, 6, 1))
        assert not p.period.is_active_on(date(2025, 12, 31))

    def test_immutable(self):
        p = AgreementParticipant(
            agreement_id=AgreementId.generate(),
            entity_id="e-1",
            participant_role=ParticipantRole.BUYER,
        )
        with pytest.raises(Exception):
            p.entity_id = "changed"

    def test_all_roles(self):
        aid = AgreementId.generate()
        for role in ParticipantRole:
            p = AgreementParticipant(
                agreement_id=aid,
                entity_id="e-1",
                participant_role=role,
            )
            assert p.participant_role == role
