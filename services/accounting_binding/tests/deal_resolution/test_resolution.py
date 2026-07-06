"""Tests — Deal Resolution Engine v1.7.

Covers:
- exact cadastral match
- same property different transaction (lease vs sale)
- same parties different property
- duplicate upload detection
- low confidence review
- multiple candidate deals
- property identity extraction
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from domain.property.property_identity import PropertyIdentity
from domain.deal_resolution.fingerprint import (
    DocumentFingerprint,
    TransactionFingerprint,
    MatchingEvidence,
    SimilarityResult,
    ConfidenceLevel,
)
from domain.deal_resolution.candidate_finder import CandidateFinder, CandidateTransaction
from domain.deal_resolution.similarity_scorer import SimilarityScorer
from domain.deal_resolution.resolver import DealResolver, Decision, ResolutionResult


# ── Fixtures ──

SAMPLE_CADASTRAL = "78:10:0005522:3018"
SAMPLE_ADDRESS = "г. Санкт-Петербург, Петроградская наб, дом 18, корп. 3, лит. В, пом. 20-Н"


def make_property(cadastral: str = SAMPLE_CADASTRAL, address: str = SAMPLE_ADDRESS) -> PropertyIdentity:
    return PropertyIdentity(cadastral_number=cadastral, normalized_address=address, area=150.5, object_type="commercial")


def make_fingerprint(
    doc_type="contract",
    doc_role="sale_contract",
    buyer="Покупатель ООО",
    seller="Шульгина Ирина Юрьевна",
    amount=Decimal("5000000"),
    contract_date=date(2026, 5, 26),
    contract_number="2182-НП/И",
    prop: PropertyIdentity | None = None,
    parties: list[dict] | None = None,
) -> DocumentFingerprint:
    return DocumentFingerprint(
        document_type=doc_type,
        document_role=doc_role,
        buyer=buyer,
        seller=seller,
        amount=amount,
        contract_date=contract_date,
        contract_number=contract_number,
        property_identity=prop or make_property(),
        parties=parties or [
            {"identity": {"name": seller}, "relation": {"role": "our_side", "relation": "our_side"}},
            {"identity": {"name": buyer}, "relation": {"role": "counterparty", "relation": "external"}},
        ],
    )


# ── Property Identity Tests ──

class TestPropertyIdentity:
    def test_cadastral_extraction(self):
        text = "Кадастровый номер: 78:10:0005522:3018"
        assert PropertyIdentity.extract_cadastral(text) == SAMPLE_CADASTRAL

    def test_address_normalization(self):
        raw = "г. СПб, Петроградская наб., д. 18"
        norm = PropertyIdentity.normalize_address(raw)
        assert "город" in norm
        assert "набережная" in norm
        assert "дом" in norm

    def test_identity_hash_deterministic(self):
        a = make_property()
        b = make_property()
        assert a.identity_hash == b.identity_hash

    def test_similarity_exact_match(self):
        a = make_property()
        b = make_property()
        assert a.similarity_to(b) > 0.99

    def test_similarity_different_cadastral(self):
        a = make_property("78:10:0005522:3018")
        b = make_property("78:10:0005522:9999")
        assert a.similarity_to(b) < 0.8


# ── Transaction Fingerprint Tests ──

class TestTransactionFingerprint:
    def test_direction_purchase(self):
        """OUR_SIDE (Шульгина) is the seller → direction is sale (мы продаём)."""
        fp = make_fingerprint(seller="Шульгина Ирина Юрьевна")
        tx = TransactionFingerprint.from_document_fingerprint(fp)
        assert tx.transaction_direction == "sale"

    def test_hash_deterministic(self):
        fp = make_fingerprint()
        tx1 = TransactionFingerprint.from_document_fingerprint(fp)
        tx2 = TransactionFingerprint.from_document_fingerprint(fp)
        assert tx1.transaction_hash == tx2.transaction_hash

    def test_fingerprint_version(self):
        fp = make_fingerprint()
        assert fp.fingerprint_version == 1


# ── Fake Store for CandidateFinder ──

class FakeDealStore:
    def __init__(self):
        self._deals: list[dict] = []

    def add(self, deal: dict):
        self._deals.append(deal)

    async def find_by_cadastral(self, cadastral: str) -> list[dict]:
        return [d for d in self._deals if d.get("cadastral_number") == cadastral]

    async def find_by_address(self, address: str) -> list[dict]:
        return [d for d in self._deals if d.get("address") and address and address.lower() in d["address"].lower()]

    async def find_by_parties(self, buyer: str, seller: str, inn: str) -> list[dict]:
        return [d for d in self._deals if (buyer and buyer.lower() in d.get("buyer", "").lower()) or (seller and seller.lower() in d.get("seller", "").lower())]

    async def find_by_contract(self, contract_number: str) -> list[dict]:
        return [d for d in self._deals if d.get("contract_number") == contract_number]

    async def find_by_date_range(self, doc_date: date | None, days: int = 30) -> list[dict]:
        return []


# ── CandidateFinder Tests ──

class TestCandidateFinder:
    @pytest.mark.asyncio
    async def test_find_by_cadastral(self):
        store = FakeDealStore()
        store.add({"id": "deal-1", "deal_type": "purchase", "title": "Test", "status": "initiated",
                    "cadastral_number": SAMPLE_CADASTRAL, "address": SAMPLE_ADDRESS,
                    "buyer": "Покупатель", "seller": "Продавец"})
        finder = CandidateFinder(store)
        fp = TransactionFingerprint(property_identity=make_property(), buyer="Покупатель")
        candidates = await finder.find_candidates(fp)
        assert len(candidates) == 1
        assert candidates[0].deal_id == "deal-1"


# ── SimilarityScorer Tests ──

class TestSimilarityScorer:
    @pytest.mark.asyncio
    async def test_exact_match_high_score(self):
        fp = TransactionFingerprint(
            transaction_type="sale_contract",
            transaction_direction="purchase",
            property_identity=make_property(),
            buyer="Покупатель",
            seller="Продавец",
            amount=Decimal("5000000"),
            contract_date=date(2026, 5, 26),
        )
        candidate = CandidateTransaction(
            deal_id="deal-1", deal_type="purchase", title="", status="", lifecycle_stage="",
            cadastral_number=SAMPLE_CADASTRAL, address=SAMPLE_ADDRESS,
            buyer="Покупатель", seller="Продавец", amount=5000000,
            contract_date=date(2026, 5, 26),
        )
        scorer = SimilarityScorer()
        result = await scorer.score(fp, candidate)
        assert result.score >= 90
        assert result.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)

    @pytest.mark.asyncio
    async def test_different_property_low_score(self):
        fp = TransactionFingerprint(
            transaction_type="sale_contract",
            property_identity=make_property("78:10:0005522:3018", "Address A"),
            buyer="Покупатель", seller="Продавец",
        )
        candidate = CandidateTransaction(
            deal_id="deal-2", deal_type="purchase", title="", status="", lifecycle_stage="",
            cadastral_number="78:10:0005522:9999", address="Address B",
            buyer="Другой", seller="Иной",
        )
        scorer = SimilarityScorer()
        result = await scorer.score(fp, candidate)
        assert result.score < 60
        assert result.confidence == ConfidenceLevel.LOW

    @pytest.mark.asyncio
    async def test_same_property_different_transaction(self):
        """Same cadastral, different transaction type (lease vs purchase)."""
        fp = TransactionFingerprint(
            transaction_type="lease",
            transaction_direction="lease",
            property_identity=make_property(),
            buyer="Тест", seller="Тест2",
            amount=Decimal("100000"),
            contract_date=date(2026, 6, 1),
        )
        candidate = CandidateTransaction(
            deal_id="deal-3", deal_type="purchase", title="", status="", lifecycle_stage="",
            cadastral_number=SAMPLE_CADASTRAL, address=SAMPLE_ADDRESS,
            buyer="Тест", seller="Тест2", amount=5000000,
        )
        scorer = SimilarityScorer()
        result = await scorer.score(fp, candidate)
        # Cadastral matches (45) + address (20) + parties (10) = 75
        assert 40 <= result.score <= 80


# ── DealResolver Tests ──

class TestDealResolver:
    @pytest.mark.asyncio
    async def test_auto_attach_with_exact_match(self):
        store = FakeDealStore()
        store.add({"id": "deal-exact", "deal_type": "purchase", "title": "Покупка - тест",
                    "status": "initiated", "lifecycle_stage": "deal_candidate",
                    "cadastral_number": SAMPLE_CADASTRAL, "address": SAMPLE_ADDRESS,
                    "buyer": "Покупатель ООО", "seller": "Шульгина Ирина Юрьевна",
                    "contract_number": "2182-НП/И",
                    "contract_date": date(2026, 5, 26), "price": 5000000})
        finder = CandidateFinder(store)
        resolver = DealResolver(finder)
        # OUR_SIDE is buyer (Покупатель ООО) → direction = purchase
        doc_fp = make_fingerprint(
            buyer="Покупатель ООО",
            seller="Продавец ООО",
            parties=[
                {"identity": {"name": "Покупатель ООО"}, "relation": {"role": "our_side", "relation": "our_side"}},
                {"identity": {"name": "Продавец ООО"}, "relation": {"role": "counterparty", "relation": "external"}},
            ],
        )
        result = await resolver.resolve(doc_fp)
        assert result.decision == Decision.AUTO_ATTACH
        assert result.matched_deal_id == "deal-exact"

    @pytest.mark.asyncio
    async def test_create_new_deal_no_match(self):
        store = FakeDealStore()
        finder = CandidateFinder(store)
        resolver = DealResolver(finder)
        doc_fp = make_fingerprint(
            buyer="Неизвестный", seller="Другой",
            prop=PropertyIdentity(cadastral_number="99:99:9999999:9999", normalized_address="Улица Неизвестная"),
        )
        result = await resolver.resolve(doc_fp)
        assert result.decision == Decision.CREATE_NEW_DEAL

    @pytest.mark.asyncio
    async def test_multiple_candidates(self):
        store = FakeDealStore()
        store.add({"id": "deal-a", "deal_type": "purchase", "title": "Сделка A",
                    "status": "initiated", "lifecycle_stage": "deal_candidate",
                    "cadastral_number": SAMPLE_CADASTRAL, "address": SAMPLE_ADDRESS,
                    "buyer": "Покупатель ООО", "seller": "Шульгина Ирина Юрьевна",
                    "contract_number": "2182-НП/И", "price": 5000000})
        store.add({"id": "deal-b", "deal_type": "lease", "title": "Аренда",
                    "status": "initiated", "lifecycle_stage": "deal_candidate",
                    "cadastral_number": SAMPLE_CADASTRAL, "address": SAMPLE_ADDRESS,
                    "buyer": "Арендатор", "seller": "Шульгина Ирина Юрьевна",
                    "contract_number": "LEASE-001", "price": 100000})
        finder = CandidateFinder(store)
        resolver = DealResolver(finder)
        # OUR_SIDE is buyer → direction = purchase
        doc_fp = make_fingerprint(
            buyer="Покупатель ООО",
            seller="Продавец ООО",
            parties=[
                {"identity": {"name": "Покупатель ООО"}, "relation": {"role": "our_side", "relation": "our_side"}},
                {"identity": {"name": "Продавец ООО"}, "relation": {"role": "counterparty", "relation": "external"}},
            ],
        )
        result = await resolver.resolve(doc_fp)
        assert result.candidate_count == 2
        assert result.decision == Decision.AUTO_ATTACH

    @pytest.mark.asyncio
    async def test_same_parties_different_properties(self):
        """Same buyer/seller, completely different property → medium score."""
        store = FakeDealStore()
        store.add({"id": "deal-other", "deal_type": "purchase", "title": "Другая сделка",
                    "status": "initiated", "lifecycle_stage": "deal_candidate",
                    "cadastral_number": "78:10:9999999:9999", "address": "Другой адрес",
                    "buyer": "Покупатель ООО", "seller": "Шульгина Ирина Юрьевна", "price": 3000000})
        finder = CandidateFinder(store)
        resolver = DealResolver(finder)
        doc_fp = make_fingerprint()
        result = await resolver.resolve(doc_fp)
        # Matches by parties (10) + type (15) + direction (10) = 35
        assert result.decision == Decision.CREATE_NEW_DEAL

    @pytest.mark.asyncio
    async def test_resolution_result_has_evidence(self):
        store = FakeDealStore()
        store.add({"id": "deal-evidence", "deal_type": "purchase", "title": "С evidence",
                    "status": "initiated", "lifecycle_stage": "deal_candidate",
                    "cadastral_number": SAMPLE_CADASTRAL, "address": SAMPLE_ADDRESS,
                    "buyer": "Покупатель ООО", "seller": "Шульгина Ирина Юрьевна",
                    "contract_number": "2182-НП/И", "price": 5000000})
        finder = CandidateFinder(store)
        resolver = DealResolver(finder)
        doc_fp = make_fingerprint()
        result = await resolver.resolve(doc_fp)
        assert len(result.evidence) > 0
        assert any(e["field"] == "cadastral_number" for e in result.evidence)
        assert any(e["field"] == "parties" for e in result.evidence)
