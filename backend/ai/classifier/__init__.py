"""Document classifier — determines document type.

Strategies (in order):
1. Rules: filename patterns, metadata keywords
2. Embeddings: cosine similarity to known document templates
3. LLM: DeepSeek for ambiguous documents
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.core.logging import get_logger

logger = get_logger("knowledge")


SUPPORTED_CLASSES = [
    "passport",
    "egrn",
    "contract",
    "power_of_attorney",
    "receipt",
    "bank_document",
    "tax_document",
    "communication",
    "commercial_offer",
    "unknown",
]

CLASS_KEYWORDS: dict[str, list[str]] = {
    "passport": ["паспорт", "серия", "номер", "выдан", "отделом"],
    "egrn": ["егрн", "выписка", "кадастровый", "реестр", "недвижимости"],
    "contract": ["договор", "контракт", "купли-продажи", "аренды", "подряда"],
    "power_of_attorney": ["доверенность", "уполномочивает", "представлять"],
    "receipt": ["расписка", "квитанция", "оплата", "получено"],
    "bank_document": ["банк", "счет", "платеж", "ипотека", "кредит"],
    "tax_document": ["налог", "ифнс", "декларация", "3-ндфл"],
    "communication": ["письмо", "уведомление", "запрос", "ответ"],
    "commercial_offer": ["коммерческое", "предложение", "объект", "цена"],
}


@dataclass
class ClassificationResult:
    document_type: str = "unknown"
    confidence: float = 0.0
    strategy: str = "none"
    reasoning: str = ""
    needs_review: bool = True


class DocumentClassifier:
    """Classify documents using rule -> embedding -> LLM cascade."""

    async def classify(self, text: str, filename: str = "") -> ClassificationResult:
        # Strategy 1: Rules
        result = self._rule_classify(text, filename)
        if result.confidence >= 0.85:
            result.needs_review = False
            return result

        # Strategy 2: Embedding similarity (stub for Sprint 3A)
        # Will use multilingual-e5-small in Sprint 7
        if result.confidence < 0.5:
            logger.info("low_rule_confidence", type=result.document_type, conf=result.confidence)

        return result

    def _rule_classify(self, text: str, filename: str) -> ClassificationResult:
        text_lower = text.lower()
        filename_lower = filename.lower()

        best_type = "unknown"
        best_score = 0.0
        best_reason = ""

        for doc_type, keywords in CLASS_KEYWORDS.items():
            score = 0.0
            matches = []
            for kw in keywords:
                if kw in text_lower:
                    score += 1.0
                    matches.append(kw)
                elif kw in filename_lower:
                    score += 0.7
                    matches.append(kw)
            if matches:
                score = score / len(keywords)
                if score > best_score:
                    best_score = score
                    best_type = doc_type
                    best_reason = f"Matched keywords: {', '.join(matches[:5])}"

        return ClassificationResult(
            document_type=best_type,
            confidence=round(best_score, 3),
            strategy="rules",
            reasoning=best_reason or "No rule matches found",
        )