"""Deal Risk Assessment Service — движок оценки рисков сделки.

Risk factors:
- ownership_period: <1yr, 1-3yr, >3yr
- minor_owners: bool
- power_of_attorney: bool
- mortgage: bool
- inheritance: bool
- court_restrictions: bool
- arrests: bool
- missing_documents: list[str]
- regulatory_conflicts: list[str]
"""

from __future__ import annotations

from uuid import UUID

from structlog import get_logger

logger = get_logger(__name__)

RISK_WEIGHTS = {
    "ownership_period_short": 15,
    "ownership_period_medium": 5,
    "minor_owners": 25,
    "power_of_attorney": 20,
    "mortgage": 15,
    "inheritance": 20,
    "court_restrictions": 30,
    "arrests": 35,
    "missing_document_required": 10,
    "regulatory_conflict": 25,
}


class RiskAssessmentService:
    """Оценивает риски сделки на основе факторов."""

    def __init__(self, session=None):
        self.session = session

    async def evaluate_deal(self, deal_id: UUID, factors: dict | None = None) -> dict:
        """Оценить сделку. factors переопределяет значения по умолчанию."""
        from backend.models.deal_risk_assessment import DealRiskAssessment

        f = factors or {}
        score = 0
        reasons = []

        # Оценка факторов
        if f.get("ownership_period") == "short":
            score += RISK_WEIGHTS["ownership_period_short"]
            reasons.append("Короткий срок владения (<1 года)")
        elif f.get("ownership_period") == "medium":
            score += RISK_WEIGHTS["ownership_period_medium"]

        if f.get("minor_owners"):
            score += RISK_WEIGHTS["minor_owners"]
            reasons.append("Несовершеннолетние собственники")

        if f.get("power_of_attorney"):
            score += RISK_WEIGHTS["power_of_attorney"]
            reasons.append("Доверенность")

        if f.get("mortgage"):
            score += RISK_WEIGHTS["mortgage"]
            reasons.append("Ипотека")

        if f.get("inheritance"):
            score += RISK_WEIGHTS["inheritance"]
            reasons.append("Наследство")

        if f.get("court_restrictions"):
            score += RISK_WEIGHTS["court_restrictions"]
            reasons.append("Судебные ограничения")

        if f.get("arrests"):
            score += RISK_WEIGHTS["arrests"]
            reasons.append("Аресты")

        missing = f.get("missing_documents", [])
        if missing:
            score += len(missing) * RISK_WEIGHTS["missing_document_required"]

        conflicts = f.get("regulatory_conflicts", [])
        if conflicts:
            score += len(conflicts) * RISK_WEIGHTS["regulatory_conflict"]

        score = min(score, 100)

        if score >= 70:
            level = "CRITICAL"
        elif score >= 50:
            level = "HIGH"
        elif score >= 25:
            level = "MEDIUM"
        else:
            level = "LOW"

        recommendations = self._generate_recommendations(level, reasons, missing, conflicts)

        assessment = {
            "deal_id": str(deal_id),
            "risk_level": level,
            "risk_score": score,
            "reasons": reasons,
            "recommendations": recommendations,
        }

        if self.session:
            record = DealRiskAssessment(
                deal_id=deal_id, risk_level=level, risk_score=score,
                factors=f, score_breakdown=assessment, recommendations=recommendations,
            )
            self.session.add(record)
            await self.session.flush()

        logger.info("risk_assessment_completed", deal_id=str(deal_id), risk_level=level, risk_score=score)
        return assessment

    def calculate_score(self, factors: dict) -> float:
        """Рассчитать числовой score на основе факторов."""
        score = 0.0
        if factors.get("minor_owners"): score += 25
        if factors.get("power_of_attorney"): score += 20
        if factors.get("mortgage"): score += 15
        if factors.get("inheritance"): score += 20
        if factors.get("court_restrictions"): score += 30
        if factors.get("arrests"): score += 35
        missing = len(factors.get("missing_documents", []))
        score += missing * 10
        return min(score, 100)

    def generate_recommendations(self, assessment: dict) -> list[str]:
        """Сгенерировать рекомендации по результатам оценки."""
        return self._generate_recommendations(
            assessment.get("risk_level", "LOW"),
            assessment.get("reasons", []),
            [],
            [],
        )

    @staticmethod
    def _generate_recommendations(level: str, reasons: list[str], missing: list[str], conflicts: list[str]) -> list[str]:
        recs = []
        if level in ("HIGH", "CRITICAL"):
            recs.append("Требуется юридическая проверка")
        if "Несовершеннолетние собственники" in reasons:
            recs.append("Запросить разрешение органов опеки")
        if "Ипотека" in reasons:
            recs.append("Запросить согласие банка на продажу")
        if "Доверенность" in reasons:
            recs.append("Проверить срок и полномочия доверенности")
        if "Аресты" in reasons:
            recs.append("Снять обременения до регистрации сделки")
        if "Наследство" in reasons:
            recs.append("Проверить сроки вступления в наследство")
        if missing:
            recs.append(f"Запросить недостающие документы: {', '.join(missing)}")
        if level == "LOW":
            recs.append("Риски минимальны. Рекомендуется стандартная проверка.")
        return recs
