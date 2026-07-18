"""
DealResolver — оркестратор resolution.

Шаги:
  1. DocumentFingerprint → TransactionFingerprint
  2. CandidateFinder.find_candidates(fp)
  3. SimilarityScorer.score(fp, candidate) for each
  4. Decision: AUTO_ATTACH / REVIEW_REQUIRED / CREATE_NEW_DEAL

DealResolver НЕ создаёт сделки.
Только возвращает ResolutionResult.
Решение о promote/bind принимает API слой.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from domain.deal_resolution.fingerprint import (
    DocumentFingerprint,
    TransactionFingerprint,
    ConfidenceLevel,
    SimilarityResult,
)
from domain.deal_resolution.candidate_finder import (
    CandidateFinder,
    CandidateTransaction,
)
from domain.deal_resolution.similarity_scorer import SimilarityScorer


class Decision(str, Enum):
    AUTO_ATTACH = "auto_attach"            # ≥95 — автоматически привязать
    REVIEW_REQUIRED = "review_required"    # 80-95 — показать кандидатов
    CREATE_NEW_DEAL = "create_new_deal"     # <80 — новая сделка


class ResolutionResult:
    """Результат resolution: решение + объяснение."""

    def __init__(
        self,
        decision: Decision,
        score: float = 0.0,
        confidence: ConfidenceLevel = ConfidenceLevel.LOW,
        matched_deal_id: str | None = None,
        matched_property_id: str | None = None,
        fingerprint_version: int = 1,
        evidence: list[dict] | None = None,
        candidate_count: int = 0,
        candidates: list[CandidateTransaction] | None = None,
    ):
        self.decision = decision
        self.score = score
        self.confidence = confidence
        self.matched_deal_id = matched_deal_id
        self.matched_property_id = matched_property_id
        self.fingerprint_version = fingerprint_version
        self.evidence = evidence or []
        self.candidate_count = candidate_count
        self.candidates = candidates or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "score": self.score,
            "confidence": self.confidence.value,
            "matched_deal_id": self.matched_deal_id,
            "matched_property_id": self.matched_property_id,
            "fingerprint_version": self.fingerprint_version,
            "resolution_reasons": self.evidence,
            "candidate_count": self.candidate_count,
            "candidates": [c.to_dict() for c in self.candidates],
        }


class DealResolver:
    """Оркестратор resolution документа.

    Read-only — не создаёт сделки.
    """

    AUTO_ATTACH_THRESHOLD = 95.0
    REVIEW_THRESHOLD = 80.0

    def __init__(
        self,
        candidate_finder: CandidateFinder,
        similarity_scorer: SimilarityScorer | None = None,
    ):
        self._finder = candidate_finder
        self._scorer = similarity_scorer or SimilarityScorer()

    async def resolve(
        self,
        doc_fp: DocumentFingerprint,
    ) -> ResolutionResult:
        """Разрешить: найти сделку или создать новую.

        Args:
            doc_fp: Отпечаток документа от OCR + Semantic Intelligence

        Returns:
            ResolutionResult с решением
        """
        # 1. Convert to transaction fingerprint
        tx_fp = TransactionFingerprint.from_document_fingerprint(doc_fp)

        # 2. Find candidates
        candidates = await self._finder.find_candidates(tx_fp)

        if not candidates:
            return ResolutionResult(
                decision=Decision.CREATE_NEW_DEAL,
                score=0.0,
                fingerprint_version=tx_fp.fingerprint_version,
                evidence=[],
                candidate_count=0,
            )

        # 3. Score each candidate
        best: tuple[CandidateTransaction, SimilarityResult] | None = None
        for candidate in candidates:
            sim = await self._scorer.score(tx_fp, candidate)
            if best is None or sim.score > best[1].score:
                best = (candidate, sim)

        if best is None:
            return ResolutionResult(
                decision=Decision.CREATE_NEW_DEAL,
                score=0.0,
                fingerprint_version=tx_fp.fingerprint_version,
                evidence=[],
                candidate_count=len(candidates),
                candidates=candidates,
            )

        best_candidate, best_sim = best

        # 4. Decision
        if best_sim.score >= self.AUTO_ATTACH_THRESHOLD:
            decision = Decision.AUTO_ATTACH
        elif best_sim.score >= self.REVIEW_THRESHOLD:
            decision = Decision.REVIEW_REQUIRED
        else:
            decision = Decision.CREATE_NEW_DEAL

        return ResolutionResult(
            decision=decision,
            score=best_sim.score,
            confidence=best_sim.confidence,
            matched_deal_id=best_candidate.deal_id if decision in (Decision.AUTO_ATTACH, Decision.REVIEW_REQUIRED) else None,
            fingerprint_version=tx_fp.fingerprint_version,
            evidence=best_sim.reasons,
            candidate_count=len(candidates),
            candidates=candidates,
        )
