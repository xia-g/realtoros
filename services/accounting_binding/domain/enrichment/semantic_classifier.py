"""
Document Semantic Reclassification v1.5.2.

OCR classification + Accounting semantic classification = final document_type.

OCR может ошибаться (например, ДКП → invoice, confidence 0.45).
Семантический анализ по содержанию документа исправляет.

Не меняет: OCR, normalized_document, journal_entry.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# Карта замены для OCR-ошибок: Latin → Cyrillic
_OCR_FIX = str.maketrans({
    'A': 'А', 'a': 'а',
    'B': 'В', 'b': 'в',  # только строчная 'в'!
    'C': 'С', 'c': 'с',
    'E': 'Е', 'e': 'е',
    'H': 'Н', 'h': 'н',
    'K': 'К', 'k': 'к',
    'M': 'М', 'm': 'м',
    'O': 'О', 'o': 'о',
    'P': 'Р', 'p': 'р',
    'T': 'Т', 't': 'т',
    'X': 'Х', 'x': 'х',
    'Y': 'У', 'y': 'у',
})


def _normalize(text: str) -> str:
    """Нормализовать OCR-текст: заменить Latin → Cyrillic, убрать лишние пробелы."""
    text = text.translate(_OCR_FIX)
    text = re.sub(r'\s+', ' ', text)
    return text.lower()


# Документы и их ключевые признаки в тексте
SEMANTIC_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "contract": [
        (r"договор\s+купли[-\s]*продажи", 0.98),
        (r"д[кп]\s*№?\s*\d", 0.95),
        (r"договор\s+(?:аренды|подряда|оказания|поставки|поручения|комиссии)", 0.92),
        (r"продавец\s*:|покупатель\s*:", 0.85),
        (r"настоящий\s+договор", 0.80),
        (r"предмет\s+договора", 0.80),
        (r"цена\s+договора\s*:", 0.75),
        (r"стоимость\s+(?:объекта|имущества|помещения)", 0.70),
        (r"переход[а]?\s+прав[а]?\s+собственности", 0.70),
        (r"свидетельство\s+о\s+государственной\s+регистрации", 0.65),
        # OCR-tolerant patterns
        (r"договор.*?купли.*?продажи", 0.90),
        (r"договор.*?нежил", 0.75),
        (r"купли.*?продажи.*?недвижим", 0.85),
        (r"купли.*?продажи.*?помещен", 0.80),
        (r"договор.*?помещен", 0.70),
        (r"дкп\s*\d", 0.90),
    ],
    "invoice": [
        (r"счет[-\s]*фактур[аы]", 0.95),
        (r"счёт\s+на\s+оплату", 0.95),
        (r"invoice\s*№", 0.90),
        (r"итого\s+к\s+оплате", 0.80),
        (r"к\s+оплате\s*:", 0.75),
        (r"плательщик\s*:", 0.70),
        (r"получатель\s*:", 0.65),
    ],
    "act": [
        (r"акт\s+(?:выполненных|приема[-\s]*передачи|сдачи[-\s]*приемки)", 0.95),
        (r"акт\s+№?\s*\d", 0.85),
        (r"принял\s*:|сдал\s*:", 0.75),
        (r"работ[ыа]\s+выполнен[ыа]", 0.70),
        (r"претензий\s+не\s+имею", 0.70),
    ],
    "payment_order": [
        (r"плат[её]жн[аяо]е?\s+поручени[ея]", 0.95),
        (r"платежное\s+поручение\s+№", 0.95),
        (r"назначение\s+платежа\s*:", 0.85),
        (r"б[и]к\s+\d{9}", 0.80),
        (r"р\s*/?\s*сч[её]т\s+\d{20}", 0.80),
        (r"к\s*/?\s*сч[её]т\s+\d{20}", 0.75),
    ],
    "property_doc": [
        (r"выписк[аи]\s+из\s+егрн", 0.98),
        (r"выписка\s+из\s+единого\s+государственного", 0.95),
        (r"кадастров[ыы]\s+(?:номер|паспорт|стоимость)", 0.90),
        (r"свидетельство\s+о\s+праве\s+собственности", 0.90),
        (r"егрн\s+\d{2}:\d{2}:\d{7}", 0.85),
        (r"кадастровый\s+номер\s*\d{2}\s*:\s*\d{2}\s*:\s*\d{7}", 0.85),
    ],
    "receipt": [
        (r"кассов[ыи][йе]\s+чек", 0.95),
        (r"квитанци[яи]\s+№", 0.90),
        (r"фискальный\s+признак", 0.85),
        (r"приходны[йй]\s+кассовы[йй]\s+ордер", 0.85),
    ],
    "bank_statement": [
        (r"банковск[аяой]\s+выписк[аи]", 0.95),
        (r"выписк[аи]\s+по\s+счет[уе]", 0.90),
        (r"движение\s+денежных\s+средств", 0.80),
    ],
    "municipal_contract": [
        (r"муниципальн[ыы]\s+контракт", 0.95),
        (r"государственн[ыы]\s+контракт", 0.90),
        (r"федеральный\s+закон\s+44[-\s]*фз", 0.85),
        (r"результат[а]?\s+торгов", 0.80),
        (r"аукцион[а]?\s+№", 0.75),
    ],
}


@dataclass
class SemanticClassification:
    """Результат семантической реклассификации."""
    ocr_type: str = "unknown"
    ocr_confidence: float = 0.0
    semantic_type: str = "unknown"
    semantic_confidence: float = 0.0
    final_type: str = "unknown"
    final_confidence: float = 0.0
    matched_patterns: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)


class SemanticReclassifier:
    """Семантическая реклассификация документа по содержанию.

    OCR classification + Semantic analysis = final document_type.

    Детерминированно: same text → same classification.
    """

    def classify(self, raw_text: str, ocr_type: str = "", ocr_confidence: float = 0.0) -> SemanticClassification:
        """Классифицировать документ по тексту.

        Args:
            raw_text: Извлечённый текст документа
            ocr_type: Оригинальный тип от OCR
            ocr_confidence: Уверенность OCR

        Returns:
            SemanticClassification с final_type
        """
        if not raw_text:
            return SemanticClassification(ocr_type=ocr_type, ocr_confidence=ocr_confidence)

        text_lower = _normalize(raw_text)
        matched_patterns: list[str] = []
        signals: list[str] = []

        best_type = "unknown"
        best_score = 0.0
        best_pattern = ""
        doc_count: dict[str, int] = {}  # how many times each type matched

        # Проверить все паттерны
        for doc_type, patterns in SEMANTIC_PATTERNS.items():
            for pattern, confidence in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    weight = confidence
                    matched_text = match.group(0)[:60]

                    # Counter for repeated type matches
                    doc_count.setdefault(doc_type, 0)
                    doc_count[doc_type] += 1

                    if doc_type == best_type:
                        # Linear boost: +0.03 per extra match, capped at 1.0
                        weight = min(confidence + 0.03 * (doc_count[doc_type] - 1), 1.0)

                    if weight > best_score:
                        best_score = weight
                        best_type = doc_type
                        best_pattern = matched_text

                    matched_patterns.append(f"{doc_type}:{matched_text}")
                    signals.append(f"Pattern '{pattern}' matched → {doc_type} ({confidence:.2f})")

        # Если ничего не найдено
        if best_type == "unknown":
            signals.append("No semantic patterns matched — using OCR type")

        # Финальное решение: комбинируем OCR и семантику
        final_type = best_type
        final_confidence = best_score

        # Если OCR высокоуверен (>> 0.8) и семантика не противоречит → доверяем OCR
        if ocr_confidence > 0.8 and (best_type == "unknown" or best_type == ocr_type):
            final_type = ocr_type
            final_confidence = max(ocr_confidence, best_score)
            signals.append(f"OCR confidence high ({ocr_confidence:.2f}) — using OCR type")

        # Если OCR и семантика согласны → повышаем уверенность
        if best_type == ocr_type and best_type != "unknown":
            final_confidence = max(ocr_confidence, best_score) * 1.1
            signals.append(f"OCR and semantic agree on '{ocr_type}' — boosted confidence")

        # Если семантика уверенно говорит одно, OCR другое → семантика побеждает
        if best_type != "unknown" and best_type != ocr_type and best_score > 0.5:
            final_type = best_type
            final_confidence = best_score
            signals.append(f"Semantic override: OCR '{ocr_type}' → semantic '{best_type}' ({best_score:.2f})")

        # Если OCR говорит unknown, берём семантику
        if (ocr_type == "unknown" or not ocr_type) and best_type != "unknown":
            final_type = best_type
            final_confidence = best_score
            signals.append(f"OCR unknown → semantic '{best_type}' ({best_score:.2f})")

        # Каппинг уверенности
        final_confidence = min(final_confidence, 1.0)

        return SemanticClassification(
            ocr_type=ocr_type or "unknown",
            ocr_confidence=round(ocr_confidence, 4),
            semantic_type=best_type,
            semantic_confidence=round(best_score, 4),
            final_type=final_type,
            final_confidence=round(final_confidence, 4),
            matched_patterns=matched_patterns,
            signals=signals,
        )
