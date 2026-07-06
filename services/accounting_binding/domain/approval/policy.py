"""
Domain — Approval Policy.

Вынесен из pipeline: пороги меняются чаще кода,
появятся правила по типу документа, налогам, суммам, рискам.

Pipeline остаётся декларативным.
"""
from __future__ import annotations

from enum import Enum

from contracts import AccountingDocument, DocumentType
from contracts.enriched_document import EnrichedDocument, CounterpartyStatus
from domain.validation.validators import ValidationResult


class ApprovalDecision(str, Enum):
    """Решение approval policy."""
    APPROVE = "approve"
    REVIEW = "review"
    REJECT = "reject"


class ApprovalPolicy:
    """Политика одобрения документов.
    
    Правила могут меняться независимо от pipeline.
    """

    # Порог confidence для auto-approve
    HIGH_CONFIDENCE = 0.8
    MIN_CONFIDENCE = 0.3

    # Типы документов, требующие обязательного review
    MANDATORY_REVIEW_TYPES: frozenset = frozenset({
        DocumentType.CONTRACT,
        DocumentType.REGISTRY_EXTRACT,
    })

    # Суммы, требующие review (VAT-sensitive)
    REVIEW_AMOUNT_THRESHOLD = 1_000_000  # 1M RUB

    def evaluate(
        self,
        validation: ValidationResult,
        enriched: EnrichedDocument,
        accounting: AccountingDocument,
    ) -> ApprovalDecision:
        """Оценить, можно ли auto-approve."""
        # 1. Если валидация не прошла → reject
        if not validation.is_valid:
            return ApprovalDecision.REJECT

        # 2. Низкий confidence → review
        if enriched.enrichment_confidence < self.MIN_CONFIDENCE:
            return ApprovalDecision.REJECT
        if enriched.enrichment_confidence < self.HIGH_CONFIDENCE:
            return ApprovalDecision.REVIEW

        # 3. Контракт/выписка → review (юридические риски)
        if enriched.document_type in self.MANDATORY_REVIEW_TYPES:
            return ApprovalDecision.REVIEW

        # 4. Большие суммы → review
        if accounting.total_debit > self.REVIEW_AMOUNT_THRESHOLD:
            return ApprovalDecision.REVIEW

        # 5. Неизвестный контрагент → review
        if enriched.counterparty.status == CounterpartyStatus.UNKNOWN:
            return ApprovalDecision.REVIEW

        # 6. Всё чисто → auto-approve
        return ApprovalDecision.APPROVE
