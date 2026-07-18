"""
ExplanationIntegrityChecker + ExplanationIntegrityReport — structural validation.

Read-only. NO fixing. NO mutation.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.business_relationship.ke_explanation import GraphExplanation


@dataclass(frozen=True)
class ExplanationIntegrityReport:
    """Отчёт о целостности объяснения. Immutable."""
    is_valid: bool = True
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class ExplanationIntegrityChecker:
    """Проверяет структуру GraphExplanation. Read-only. No fix."""

    @staticmethod
    def check(explanation: GraphExplanation) -> ExplanationIntegrityReport:
        errors: list[str] = []
        warnings: list[str] = []

        if explanation.step_count == 0:
            warnings.append("Empty explanation: no steps")

        seen_numbers = set()
        for step in explanation.steps:
            if step.step_number in seen_numbers:
                errors.append(f"Duplicate step number: {step.step_number}")
            seen_numbers.add(step.step_number)

            if not step.reasons and not step.evidence:
                warnings.append(f"Step {step.step_number}: no reasons or evidence")

        if not (0.0 <= explanation.overall_confidence <= 1.0):
            warnings.append(f"Confidence out of range: {explanation.overall_confidence}")

        return ExplanationIntegrityReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )
