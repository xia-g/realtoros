"""
DocumentRoleClassifier — pattern-based role resolution.

Определяет business-роль документа по его тексту.
НЕ меняет OCR classification — только добавляет document_role.

Паттерны основаны на русской деловой лексике.
OCR-ошибки (Latin↔Cyrillic) автоматически нормализуются.
"""
from __future__ import annotations

import re
from hashlib import sha256

from domain.document_semantics.document_role import (
    DocumentRole,
    DocumentSemantic,
    ClassificationSource,
)

# Карта нормализации OCR-ошибок: Latin → Cyrillic
_OCR_FIX = str.maketrans({
    'A': 'А', 'a': 'а',
    'B': 'В', 'C': 'С', 'c': 'с',
    'E': 'Е', 'e': 'е',
    'H': 'Н', 'K': 'К', 'k': 'к',
    'M': 'М', 'O': 'О', 'o': 'о',
    'P': 'Р', 'p': 'р',
    'T': 'Т', 'X': 'Х', 'x': 'х',
    'y': 'у',
})


def _normalize(text: str) -> str:
    """Нормализовать текст: lower + OCR fix."""
    return text.lower().translate(_OCR_FIX)


# ── Patterns: каждый паттерн → (role, confidence, description) ──

PATTERNS: dict[str, list[tuple[re.Pattern, float, str]]] = {
    "transfer_act": [
        (re.compile(r"акт[а-я]*\s+прием[а-я]*[-\s]*передач[и]?"), 0.97, "Акт приема-передачи"),
        (re.compile(r"передал[а-я]*\s*(?:объект|имуществ|недвижим)"), 0.92, "Передача объекта"),
        (re.compile(r"принял[а-я]*\s*(?:объект|имуществ|недвижим)"), 0.92, "Принятие объекта"),
        (re.compile(r"объект\s+передан"), 0.90, "Объект передан"),
        (re.compile(r"акт[а-я]*\s+(?:приемки|приема|сдачи)"), 0.88, "Акт приемки"),
        (re.compile(r"сторон[а-я]*\s+подтвержда[а-я]*"), 0.80, "Стороны подтверждают"),
    ],
    "sale_contract": [
        (re.compile(r"договор[а-я]*\s+купл[а-я]*[-\s]*продаж[а-я]*"), 0.98, "Договор купли-продажи"),
        (re.compile(r"продавец\s+обяз[а-я]*"), 0.90, "Продавец обязуется"),
        (re.compile(r"покупател[а-я]*.*?обяз[а-я]*"), 0.85, "Покупатель обязуется"),
        (re.compile(r"цен[а-я]*\s+договор[а-я]*"), 0.80, "Цена договора"),
        (re.compile(r"договор[а-я]*\s+(?:аренд[а-я]*|подряд[а-я]*)"), 0.70, "Договор (не купли-продажи)"),
    ],
    "egrn_extract": [
        (re.compile(r"выписк[а-я]*\s+из\s+егрн"), 0.98, "Выписка из ЕГРН"),
        (re.compile(r"единый\s+государственный\s+реестр\s+недвижимости"), 0.97, "ЕГРН"),
        (re.compile(r"выписк[а-я]*\s+.+?реестр[а-я]*\s+недвижимости"), 0.97, "Выписка из реестра недвижимости"),
        (re.compile(r"кадастров[а-я]*\s+(?:номер|стоимость|паспорт)"), 0.85, "Кадастровые данные"),
        (re.compile(r"выписк[а-я]*\s+из\s+(?:реестр|кадастр)"), 0.80, "Выписка из реестра"),
    ],
    "payment_order": [
        (re.compile(r"платежн[а-я]*\s+поручен[а-я]*"), 0.98, "Платежное поручение"),
        (re.compile(r"сумм[а-я]*\s+платеж[а-я]*"), 0.85, "Сумма платежа"),
        (re.compile(r"банк[а-я]*\s+(?:плательщик|получател)"), 0.80, "Банковские реквизиты"),
    ],
    "passport": [
        (re.compile(r"паспорт[а-я]*\s+(?:сери[а-я]*|номер|граждан)"), 0.95, "Паспорт"),
        (re.compile(r"удостоверени[а-я]*\s+личности"), 0.90, "Удостоверение личности"),
    ],
    "invoice": [
        (re.compile(r"счет[а-я]*\s+(?:на\s+)?оплат"), 0.95, "Счет на оплату"),
        (re.compile(r"счет[а-я]*-фактур[а-я]*"), 0.90, "Счет-фактура"),
    ],
    "receipt": [
        (re.compile(r"кассов[а-я]*\s+чек"), 0.95, "Кассовый чек"),
        (re.compile(r"товарн[а-я]*\s+чек"), 0.90, "Товарный чек"),
        (re.compile(r"авансов[а-я]*\s+отчет"), 0.85, "Авансовый отчет"),
    ],
    "certificate": [
        (re.compile(r"свидетельств[а-я]*\s+о\s+прав[а-я]*"), 0.95, "Свидетельство о праве"),
        (re.compile(r"свидетельств[а-я]*\s+о\s+регистраци"), 0.90, "Свидетельство о регистрации"),
    ],
    "reconciliation": [
        (re.compile(r"акт[а-я]*\s+сверк[а-я]*"), 0.95, "Акт сверки"),
    ],
}


class DocumentRoleClassifier:
    """Классификатор business-роли документа по тексту."""

    def classify(
        self,
        document_type: str,
        raw_text: str = "",
        ocr_confidence: float = 0.0,
    ) -> DocumentSemantic:
        """Определить document_role по тексту.

        Args:
            document_type: тип от OCR ('contract', 'invoice', 'act', ...)
            raw_text: сырой текст документа
            ocr_confidence: уверенность OCR

        Returns:
            DocumentSemantic с определённой ролью
        """
        if not raw_text:
            return DocumentSemantic(
                document_type=document_type,
                document_role=DocumentRole.UNKNOWN,
                confidence=ocr_confidence,
                source=ClassificationSource.OCR,
            )

        text_norm = _normalize(raw_text)

        # Собираем все совпадения
        matches: list[tuple[DocumentRole, float, str]] = []

        for role_key, patterns in PATTERNS.items():
            for regex, conf, desc in patterns:
                if regex.search(text_norm):
                    role = DocumentRole(role_key)
                    matches.append((role, conf, desc))

        if not matches:
            # Fallback: если document_type contract, но не sale → other_contract
            if document_type in ("contract", "municipal_contract"):
                return DocumentSemantic(
                    document_type=document_type,
                    document_role=DocumentRole.OTHER_CONTRACT,
                    confidence=max(ocr_confidence, 0.6),
                    source=ClassificationSource.OCR,
                )
            return DocumentSemantic(
                document_type=document_type,
                document_role=DocumentRole.UNKNOWN,
                confidence=ocr_confidence,
                source=ClassificationSource.OCR,
            )

        # Берём лучшее совпадение с приоритетом ролей
        # TRANSFER_ACT patterns are more specific → beat SALE_CONTRACT
        ROLE_PRIORITY = [
            DocumentRole.TRANSFER_ACT,
            DocumentRole.EGRN_EXTRACT,
            DocumentRole.PAYMENT_ORDER,
            DocumentRole.PASSPORT,
            DocumentRole.CERTIFICATE,
            DocumentRole.RECEIPT,
            DocumentRole.INVOICE,
            DocumentRole.SALE_CONTRACT,
        ]
        best_role = matches[0][0]
        best_conf = 0.0

        for role, conf, _ in matches:
            # Same role = take higher confidence
            if role == best_role and conf > best_conf:
                best_conf = conf
            # Different role = check priority
            elif role != best_role:
                best_idx = ROLE_PRIORITY.index(best_role) if best_role in ROLE_PRIORITY else 99
                role_idx = ROLE_PRIORITY.index(role) if role in ROLE_PRIORITY else 99
                if role_idx < best_idx:
                    best_role = role
                    best_conf = conf
                elif role_idx == best_idx and conf > best_conf:
                    best_conf = conf

        return DocumentSemantic(
            document_type=document_type,
            document_role=best_role,
            confidence=round(best_conf, 4),
            source=ClassificationSource.SEMANTIC,
        )

    def classify_from_fields(
        self,
        document_type: str,
        entities: dict | None = None,
        ocr_confidence: float = 0.0,
    ) -> DocumentSemantic:
        """Определить роль из entity-полей (без полного текста)."""
        raw_text = ""
        if entities and isinstance(entities, dict):
            raw_text = " ".join(str(v) for v in entities.values() if isinstance(v, (str, list)))
        return self.classify(document_type, raw_text, ocr_confidence)
