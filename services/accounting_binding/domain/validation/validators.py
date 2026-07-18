"""
Domain — Validation.

Проверяет enriched_document на:
- schema correctness
- business rules
- required fields
- confidence thresholds
- explainability
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from contracts import EnrichedDocument, AccountingDocument


@dataclass(frozen=True)
class ValidationError:
    """Детерминированная ошибка валидации."""
    code: str  # машинный код
    message: str  # человеко-читаемое описание
    field: str = ""
    value: str = ""


@dataclass(frozen=True)
class ValidationResult:
    """Результат валидации."""
    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, code: str, message: str, field: str = "", value: str = "") -> "ValidationResult":
        return ValidationResult(
            is_valid=False,
            errors=self.errors + [ValidationError(code, message, field, value)],
            warnings=self.warnings,
        )


class EnrichedDocumentValidator:
    """Валидация enriched_document перед маппингом."""

    MIN_CONFIDENCE = 0.5
    MIN_EXTRACTED_ENTITIES = 1

    def validate(self, doc: EnrichedDocument) -> ValidationResult:
        """Валидация enriched_document."""
        result = ValidationResult(is_valid=True)
        errors: list[ValidationError] = []

        # 1. Confidence threshold
        if doc.enrichment_confidence < self.MIN_CONFIDENCE:
            errors.append(ValidationError(
                code="LOW_CONFIDENCE",
                message=f"Общая уверенность ниже порога ({doc.enrichment_confidence:.2f} < {self.MIN_CONFIDENCE})",
                field="enrichment_confidence",
                value=str(doc.enrichment_confidence),
            ))

        # 2. Required fields
        if not doc.document_id:
            errors.append(ValidationError(
                code="MISSING_DOCUMENT_ID",
                message="Отсутствует document_id",
                field="document_id",
            ))

        # 3. Extracted entities threshold
        total_entities = (
            len(doc.canonical_amounts)
            + len(doc.canonical_dates)
            + len(doc.vat_numbers)
            + len(doc.ibans)
        )
        if total_entities < self.MIN_EXTRACTED_ENTITIES and doc.source != "manual":
            errors.append(ValidationError(
                code="NO_ENTITIES_EXTRACTED",
                message="Не извлечено ни одной сущности",
                field="enrichment_confidence",
                value=str(total_entities),
            ))

        # 4. Amount balance (if multiple amounts)
        if len(doc.canonical_amounts) > 1:
            amounts = [a.amount for a in doc.canonical_amounts]
            if amounts and amounts[0] != sum(amounts[1:]):
                errors.append(ValidationError(
                    code="AMOUNT_MISMATCH",
                    message="Суммы не сходятся",
                    field="canonical_amounts",
                    value=str(amounts),
                ))

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)


class AccountingDocumentValidator:
    """Валидация accounting_document перед posting."""

    def validate(self, doc: AccountingDocument) -> ValidationResult:
        """Валидация accounting_document."""
        errors: list[ValidationError] = []

        # 1. Double-entry balance
        if doc.total_debit != doc.total_credit:
            errors.append(ValidationError(
                code="UNBALANCED_ENTRY",
                message=f"Дебет ({doc.total_debit}) ≠ Кредит ({doc.total_credit})",
                field="entries",
            ))

        # 2. Required accounts
        if not doc.entries:
            errors.append(ValidationError(
                code="NO_ENTRIES",
                message="Нет бухгалтерских записей",
                field="entries",
            ))

        # 3. Company
        if not doc.company_id:
            errors.append(ValidationError(
                code="MISSING_COMPANY",
                message="Не указана компания",
                field="company_id",
            ))

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)
