"""
Tests — Document Role Resolution v1.5.4.

Coverage:
- document_type → document_role mapping
- TRANSFER_ACT detection from text
- EGRN detection
- PAYMENT_ORDER detection
- Deterministic semantic hash
- Deal requirement closure mapping
- Real ACT text → TRANSFER_ACT
"""
from __future__ import annotations

import pytest

from domain.document_semantics.document_role import DocumentRole, DocumentSemantic, ClassificationSource
from domain.document_semantics.role_classifier import DocumentRoleClassifier
from domain.deal.document_requirement_resolver import ROLE_TO_REQUIREMENT_KEY


class TestDocumentRole:
    def test_sale_contract_value(self):
        assert DocumentRole.SALE_CONTRACT.value == "sale_contract"

    def test_transfer_act_value(self):
        assert DocumentRole.TRANSFER_ACT.value == "transfer_act"

    def test_egrn_extract_value(self):
        assert DocumentRole.EGRN_EXTRACT.value == "egrn_extract"

    def test_payment_order_value(self):
        assert DocumentRole.PAYMENT_ORDER.value == "payment_order"


class TestDocumentSemantic:
    def test_semantic_hash_deterministic(self):
        a = DocumentSemantic("contract", DocumentRole.SALE_CONTRACT, 0.95, ClassificationSource.SEMANTIC)
        b = DocumentSemantic("contract", DocumentRole.SALE_CONTRACT, 0.95, ClassificationSource.SEMANTIC)
        assert a.semantic_hash == b.semantic_hash
        assert a == b

    def test_semantic_hash_differs_by_role(self):
        a = DocumentSemantic("contract", DocumentRole.SALE_CONTRACT, 0.95)
        b = DocumentSemantic("contract", DocumentRole.TRANSFER_ACT, 0.95)
        assert a.semantic_hash != b.semantic_hash

    def test_to_dict(self):
        sem = DocumentSemantic("contract", DocumentRole.SALE_CONTRACT, 0.95, ClassificationSource.SEMANTIC)
        d = sem.to_dict()
        assert d["document_type"] == "contract"
        assert d["document_role"] == "sale_contract"
        assert d["source"] == "SEMANTIC"
        assert "semantic_hash" in d


class TestRoleClassifier:
    """Pattern-based classification."""

    def test_contract_to_sale_contract(self):
        text = "ДОГОВОР КУПЛИ-ПРОДАЖИ нежилого помещения"
        result = DocumentRoleClassifier().classify("contract", text, 0.8)
        assert result.document_role == DocumentRole.SALE_CONTRACT
        assert result.source == ClassificationSource.SEMANTIC

    def test_contract_to_transfer_act(self):
        text = "АКТ ПРИЕМА-ПЕРЕДАЧИ нежилого помещения"
        result = DocumentRoleClassifier().classify("contract", text, 0.8)
        assert result.document_role == DocumentRole.TRANSFER_ACT
        assert result.source == ClassificationSource.SEMANTIC

    def test_egrn_detection(self):
        text = "ВЫПИСКА из Единого государственного реестра недвижимости"
        result = DocumentRoleClassifier().classify("certificate", text, 0.6)
        assert result.document_role == DocumentRole.EGRN_EXTRACT

    def test_payment_order_detection(self):
        text = "ПЛАТЕЖНОЕ ПОРУЧЕНИЕ № 123 от 01.02.2026"
        result = DocumentRoleClassifier().classify("payment_order", text, 0.7)
        assert result.document_role == DocumentRole.PAYMENT_ORDER

    def test_real_act_text_to_transfer_act(self):
        """Realistic ACT text — with OCR errors (Latin↔Cyrillic)."""
        text = (
            "Акт приема-передачи к Договору купли-продажи нежилого помещения\n"
            "Мы, нижеподписавшиеся, составили настоящий акт о том, что\n"
            "Продавец передал, а Покупатель принял объект недвижимости"
        )
        result = DocumentRoleClassifier().classify("contract", text, 0.8)
        assert result.document_role == DocumentRole.TRANSFER_ACT
        assert result.confidence >= 0.90

    def test_unknown_fallback(self):
        text = "Справка о доходах физического лица"
        result = DocumentRoleClassifier().classify("unknown", text, 0.5)
        assert result.document_role == DocumentRole.UNKNOWN

    def test_empty_text_returns_unknown(self):
        result = DocumentRoleClassifier().classify("contract", "", 0.5)
        assert result.document_role in (DocumentRole.UNKNOWN, DocumentRole.OTHER_CONTRACT)


class TestDealRequirementMapping:
    """DocumentRole → deal requirement key mapping."""

    def test_transfer_act_closes_acceptance_act(self):
        assert ROLE_TO_REQUIREMENT_KEY[DocumentRole.TRANSFER_ACT] == "acceptance_act"

    def test_sale_contract_closes_dkp(self):
        assert ROLE_TO_REQUIREMENT_KEY[DocumentRole.SALE_CONTRACT] == "dkp"

    def test_egrn_extract_closes_egrn(self):
        assert ROLE_TO_REQUIREMENT_KEY[DocumentRole.EGRN_EXTRACT] == "egrn_extract"

    def test_payment_order_closes_payment(self):
        assert ROLE_TO_REQUIREMENT_KEY[DocumentRole.PAYMENT_ORDER] == "payment_order"

    def test_passport_closes_seller_passport(self):
        assert ROLE_TO_REQUIREMENT_KEY[DocumentRole.PASSPORT] == "passport_seller"
