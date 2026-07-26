"""
Epic 1 / Stream 2 — Processing Pipeline unit tests.

Tests classification, extraction, and pipeline state machine.
No database needed for these.
"""
from __future__ import annotations

import sys
sys.path.insert(0, "/home/xiag/real-estate-os/services/accounting_binding")

from backend.services.processing.models import (
    PipelineRun, PipelineStep,
    validate_pipeline_transition, transition_pipeline,
    PIPELINE_STEP_ORDER,
)
from backend.services.processing.steps.classification_step import classify_text
from backend.services.processing.steps.extraction_step import extract_fields


class TestPipelineStateMachine:

    def test_pending_to_running(self):
        p = PipelineRun(status="PENDING")
        err = transition_pipeline(p, "RUNNING")
        assert err is None
        assert p.status == "RUNNING"

    def test_invalid_transition(self):
        p = PipelineRun(status="COMPLETED")
        err = transition_pipeline(p, "RUNNING")
        assert err is not None

    def test_completed_is_terminal(self):
        assert validate_pipeline_transition("COMPLETED", "RUNNING") is not None

    def test_failed_can_retry(self):
        assert validate_pipeline_transition("FAILED", "PENDING") is None

    def test_full_flow(self):
        transitions = [
            ("PENDING", "RUNNING"),
            ("RUNNING", "OCR_COMPLETED"),
            ("OCR_COMPLETED", "CLASSIFIED"),
            ("CLASSIFIED", "EXTRACTED"),
            ("EXTRACTED", "KNOWLEDGE_BOUND"),
            ("KNOWLEDGE_BOUND", "COMPLETED"),
        ]
        p = PipelineRun(status="PENDING")
        for current, target in transitions:
            assert p.status == current
            err = transition_pipeline(p, target)
            assert err is None, f"{current} → {target}: {err}"
        assert p.status == "COMPLETED"

    def test_step_order(self):
        assert PIPELINE_STEP_ORDER == ["ocr", "quality", "classification", "extraction", "knowledge"]


class TestClassification:

    def test_empty_text(self):
        result = classify_text("")
        assert result.document_type == "unknown"
        assert result.confidence == 0.0

    def test_invoice_detection(self):
        text = "Счет на оплату №123 от 01.01.2024\nПоставщик: ООО Ромашка\nСумма: 1000.00\nНДС: 200.00"
        result = classify_text(text)
        assert result.document_type == "invoice"
        assert result.confidence >= 0.4  # scaled from ~0.25 match ratio

    def test_contract_detection(self):
        text = "ДОГОВОР №45\nСтороны договорились о сотрудничестве\nПредмет договора: поставка товаров"
        result = classify_text(text)
        assert result.document_type == "contract"
        assert result.confidence > 0.5

    def test_act_detection(self):
        text = "АКТ выполненных работ №78\nПриемка выполнена\nСумма: 50000"
        result = classify_text(text)
        assert result.document_type == "act"
        assert result.confidence > 0.5

    def test_bank_statement_detection(self):
        text = "Банковская выписка за период\nОперации по счету\nБаланс: 100000"
        result = classify_text(text)
        assert result.document_type == "bank_statement"
        assert result.confidence > 0.5

    def test_unknown_document(self):
        text = "Произвольный текст без ключевых слов"
        result = classify_text(text)
        assert result.document_type == "unknown"


class TestExtraction:

    def test_empty_text(self):
        result = extract_fields("", "invoice")
        assert result["confidence"] == 0.0

    def test_invoice_extraction(self):
        text = "Счет на оплату №ИНВ-123\nПоставщик: ООО Ромашка\nПокупатель: ООО Клиент\nСумма: 1000.00\nНДС: 200.00\n01.01.2024"
        result = extract_fields(text, "invoice")
        assert "supplier" in result["fields"]
        assert "amount" in result["fields"]
        assert "vat" in result["fields"]
        assert "invoice_number" in result["fields"]
        assert "date" in result["fields"]
        assert "customer" in result["fields"]

    def test_contract_extraction(self):
        text = "Договор №Д-001 от 15.03.2024\nПоставщик: ООО Поставщик\nПокупатель: ООО Заказчик"
        result = extract_fields(text, "contract")
        assert "supplier" in result["fields"]
        assert "customer" in result["fields"]
        assert "contract_number" in result["fields"]
        assert "date" in result["fields"]

    def test_missing_fields(self):
        text = "Произвольный текст"
        result = extract_fields(text, "invoice")
        assert len(result["warnings"]) > 0
        assert result["confidence"] < 0.5
