"""Classification Step — rule-based document type detection."""
from __future__ import annotations

from backend.services.processing.models import (
    PipelineRun, PipelineStep, ClassificationResult,
)
from backend.services.processing.storage import PipelineRepository

# Document type patterns
DOCUMENT_PATTERNS: dict[str, list[str]] = {
    "invoice": [
        "счет", "invoice", "счет-фактура", "счет на оплату",
        "invoice number", "счет №", "поставщик", "supplier",
        "продавец", "seller", "итого", "total",
    ],
    "contract": [
        "договор", "contract", "соглашение", "agreement",
        "контракт", "стороны", "parties", "предмет договора",
        "купли-продажи", "продавец", "покупатель", "договор №",
    ],
    "act": [
        "акт", "act of acceptance", "акт выполненных работ",
        "acceptance certificate", "оказания услуг",
        "приемка", "выполнено",
    ],
    "bank_statement": [
        "выписка", "bank statement", "операции по счету",
        "transaction", "баланс", "balance", "движение средств",
        "поступление", "списание",
    ],
    "receipt": [
        "чек", "receipt", "кассовый чек", "фискальный",
        "касса", "приход",
    ],
    "passport": [
        "паспорт", "passport", "удостоверение личности",
        "серия",
    ],
    "power_of_attorney": [
        "доверенность", "power of attorney",
        "уполномочивает", "представлять интересы",
    ],
    "invoice": [
        "счет-фактура", "счет на оплату",
        "invoice number", "счет №", "поставщик", "supplier",
        "seller", "итого", "total",
    ],
}

REQUIRED_FIELDS: dict[str, list[str]] = {
    "invoice": ["supplier", "amount", "date"],
    "contract": ["parties", "date"],
    "act": ["parties", "date", "amount"],
    "bank_statement": ["transactions"],
    "receipt": ["amount", "date"],
    "passport": ["number", "name"],
    "power_of_attorney": ["principal", "representative"],
}


def classify_text(raw_text: str) -> ClassificationResult:
    """Classify document type based on keyword matching."""
    if not raw_text:
        return ClassificationResult(
            document_type="unknown", confidence=0.0,
        )

    # Normalize OCR text: newlines break multi-word keyword matching
    normalized = raw_text.replace("\\n", " ").replace("\n", " ").replace("\r", " ")
    text_lower = normalized.lower()
    scores: list[tuple[str, float]] = []

    for doc_type, keywords in DOCUMENT_PATTERNS.items():
        found = sum(1 for kw in keywords if kw.lower() in text_lower)
        score = found / len(keywords) if keywords else 0
        scores.append((doc_type, score))

    scores.sort(key=lambda x: x[1], reverse=True)

    if not scores or scores[0][1] <= 0:
        return ClassificationResult(
            document_type="unknown", confidence=0.0,
        )

    best_type, best_score = scores[0]
    alternatives = [(t, s) for t, s in scores[1:4] if s > 0]

    return ClassificationResult(
        document_type=best_type,
        confidence=min(1.0, best_score * 2),  # scale up for readability
        alternatives=alternatives,
    )


def execute_classification_step(
    pipeline: PipelineRun,
    step: PipelineStep,
    repo: PipelineRepository,
) -> tuple[bool, dict | str]:
    """Execute classification step on OCR result."""
    # Get OCR result from previous step
    steps = repo.get_steps(pipeline.pipeline_id)
    ocr_step = next((s for s in steps if s.step_type == "ocr"), None)
    if not ocr_step or not ocr_step.result:
        return False, "No OCR result available for classification"

    raw_text = ocr_step.result.get("ocr", {}).get("raw_text", "") or ocr_step.result.get("ocr", {}).get("raw_text_preview", "")

    result = classify_text(raw_text)

    return True, {
        "document_type": result.document_type,
        "confidence": result.confidence,
        "alternatives": [{"type": t, "score": s} for t, s in result.alternatives],
    }
