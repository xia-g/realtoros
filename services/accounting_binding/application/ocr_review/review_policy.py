"""
OCR Review Policy — правила для auto-approve vs manual review.

Правила:
  semantic_confidence >= 0.90
  AND party_identity resolved
  AND ocr_confidence >= 0.40
  → AUTO_APPROVE_ALLOWED

Иначе:
  → MANUAL_REVIEW_REQUIRED

AUTO_APPROVE_ALLOWED ≠ auto-approve.
Это сигнал что approve безопасен, но решение за человеком.
"""
from __future__ import annotations

from dataclasses import dataclass


class ReviewDecision:
    """Решение по review."""
    AUTO_APPROVE_ALLOWED = "auto_approve_allowed"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


@dataclass
class ReviewPolicyResult:
    """Результат оценки policy."""
    decision: str = ReviewDecision.MANUAL_REVIEW_REQUIRED
    reasons: list[str] | None = None


class ReviewPolicy:
    """Политика ревью OCR результатов.

    Детерминирована: одинаковый вход → одинаковое решение.
    """

    SEMANTIC_THRESHOLD = 0.90
    OCR_THRESHOLD = 0.40

    def evaluate(
        self,
        ocr_confidence: float = 0.0,
        semantic_confidence: float = 0.0,
        parties_resolved: bool = False,
        ocr_status: str = "",
    ) -> ReviewPolicyResult:
        """Оценить, требуется ли human review.

        Args:
            ocr_confidence: confidence от OCR (overall_confidence)
            semantic_confidence: confidence от SemanticReclassifier
            parties_resolved: хотя бы одна сторона сделки определена
            ocr_status: статус от OCR Node ('completed' или 'need_review')

        Returns:
            ReviewPolicyResult с решением
        """
        reasons: list[str] = []

        # Если OCR completed — auto-approve
        if ocr_status == "completed":
            return ReviewPolicyResult(
                decision=ReviewDecision.AUTO_APPROVE_ALLOWED,
                reasons=["OCR status: completed"],
            )

        # Проверка условий для auto-approve
        auto_allowed = True

        if semantic_confidence < self.SEMANTIC_THRESHOLD:
            reasons.append(
                f"semantic_confidence {semantic_confidence:.2f} < {self.SEMANTIC_THRESHOLD}"
            )
            auto_allowed = False

        if ocr_confidence < self.OCR_THRESHOLD:
            reasons.append(
                f"ocr_confidence {ocr_confidence:.2f} < {self.OCR_THRESHOLD}"
            )
            auto_allowed = False

        if not parties_resolved:
            reasons.append("no parties resolved")
            auto_allowed = False

        if auto_allowed:
            return ReviewPolicyResult(
                decision=ReviewDecision.AUTO_APPROVE_ALLOWED,
                reasons=reasons or ["All thresholds met"],
            )

        return ReviewPolicyResult(
            decision=ReviewDecision.MANUAL_REVIEW_REQUIRED,
            reasons=reasons,
        )
