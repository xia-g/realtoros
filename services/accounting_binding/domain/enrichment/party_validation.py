"""
Validation — Party Identity rules.

Добавляет проверки:
OK: Individual + IP
WARNING: Individual without legal status
ERROR: same transaction: party_role=OUR_SIDE AND counterparty=true (self-deal)
"""
from __future__ import annotations

from contracts import EnrichedDocument
from domain.validation.validators import ValidationResult, ValidationError


class PartyValidationRule:
    """Валидация участников сделки."""

    @staticmethod
    def validate(doc: EnrichedDocument) -> ValidationResult:
        """Проверить участников сделки."""
        errors: list[ValidationError] = []
        warnings: list[str] = []

        if not doc.parties:
            return ValidationResult(is_valid=True)

        has_our_side = False
        has_counterparty = False
        has_individual_without_status = False

        for p in doc.parties:
            identity = p.get("identity", {})
            relation = p.get("relation", {})

            entity_type = identity.get("entity_type", "")
            relation_type = relation.get("relation", "")
            role = relation.get("role", "")
            confidence = identity.get("confidence", 0)

            # OUR_SIDE detection
            if relation_type == "our_side" or role == "our_side":
                has_our_side = True

            # COUNTERPARTY detection
            if relation_type == "external" or role == "counterparty":
                has_counterparty = True

            # INDIVIDUAL without legal status → WARNING
            if entity_type == "individual" and confidence < 0.5:
                has_individual_without_status = True
                warnings.append(
                    f"Физическое лицо без правового статуса: {identity.get('name', '')}"
                )

        # Self-deal check
        if has_our_side and has_counterparty:
            errors.append(ValidationError(
                code="SELF_DEAL_DETECTED",
                message="Сделка с самим собой: участник одновременно OUR_SIDE и COUNTERPARTY",
                field="parties",
            ))

        # IP warning
        if has_individual_without_status:
            warnings.append("Рекомендуется уточнить правовой статус физического лица")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
