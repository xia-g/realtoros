"""
OCR Review Service — approve/reject/review_required.

approve():
  PATCH OCR Node
  → review_state = APPROVED
  → outbox event
  → pipeline продолжается

reject():
  → review_state = REJECTED
  → outbox event

review_required():
  → review_state = REQUIRED
  → outbox event
  → UI показывает кнопки Approve/Reject

НЕ делает approve автоматически.
НЕ считает need_review ошибкой.
"""
from __future__ import annotations

import logging
from typing import Protocol

import httpx

from application.ocr_review.review_policy import ReviewPolicy, ReviewDecision, ReviewPolicyResult
from application.ocr_review.review_state import OCRReviewState

logger = logging.getLogger(__name__)

OCR_NODE_URL = "http://192.168.1.113:8000/api/v1"


class OutboxPublisher(Protocol):
    """Протокол outbox для событий ревью."""
    async def publish(self, event_type: str, payload: dict) -> None: ...


class ReviewStore(Protocol):
    """Протокол хранения состояния ревью."""
    async def get_review_state(self, job_id: str) -> OCRReviewState | None: ...
    async def set_review_state(self, job_id: str, state: OCRReviewState) -> None: ...


class OCRReviewService:
    """Сервис ревью OCR результатов."""

    def __init__(
        self,
        policy: ReviewPolicy | None = None,
        outbox: OutboxPublisher | None = None,
        store: ReviewStore | None = None,
    ):
        self._policy = policy or ReviewPolicy()
        self._outbox = outbox
        self._store = store
        self._ocr_node_url = OCR_NODE_URL

    async def approve(self, job_id: str) -> bool:
        """Approve OCR результат.

        Делает PATCH на OCR Node → сохраняет событие → возвращает True/False.
        """
        logger.info("OCR Review: approving job=%s", job_id[:8])

        # 1. PATCH OCR Node
        try:
            async with httpx.AsyncClient(timeout=10, proxy=None, trust_env=False) as client:
                resp = await client.patch(f"{self._ocr_node_url}/jobs/{job_id}/approve")
                if resp.status_code != 200:
                    logger.error("OCR Node approve failed: %d %s", resp.status_code, resp.text[:200])
                    return False
        except Exception as e:
            logger.error("OCR Node approve error: %s", e)
            return False

        # 2. Сохранить состояние
        if self._store:
            await self._store.set_review_state(job_id, OCRReviewState.APPROVED)

        # 3. Событие
        if self._outbox:
            await self._outbox.publish("OCR_REVIEW_APPROVED", {
                "job_id": job_id,
                "approved_at": str(__import__("datetime").datetime.utcnow()),
            })

        logger.info("OCR Review: approved job=%s", job_id[:8])
        return True

    async def reject(self, job_id: str, reason: str = "") -> bool:
        """Reject OCR результат."""
        logger.info("OCR Review: rejecting job=%s", job_id[:8])

        if self._store:
            await self._store.set_review_state(job_id, OCRReviewState.REJECTED)

        if self._outbox:
            await self._outbox.publish("OCR_REVIEW_REJECTED", {
                "job_id": job_id,
                "reason": reason or "Rejected by user",
            })

        logger.info("OCR Review: rejected job=%s reason=%s", job_id[:8], reason[:50] if reason else "")
        return True

    async def review_required(self, job_id: str, ocr_confidence: float = 0.0) -> None:
        """Отметить что требуется human review."""
        if self._store:
            await self._store.set_review_state(job_id, OCRReviewState.REQUIRED)

        if self._outbox:
            await self._outbox.publish("OCR_REVIEW_REQUIRED", {
                "job_id": job_id,
                "ocr_confidence": ocr_confidence,
                "review_url": f"/imports/documents?review={job_id}",
            })

    async def evaluate_and_notify(
        self,
        job_id: str,
        ocr_confidence: float = 0.0,
        semantic_confidence: float = 0.0,
        parties_resolved: bool = False,
        ocr_status: str = "",
    ) -> ReviewPolicyResult:
        """Оценить policy и при необходимости запросить review."""
        result = self._policy.evaluate(
            ocr_confidence=ocr_confidence,
            semantic_confidence=semantic_confidence,
            parties_resolved=parties_resolved,
            ocr_status=ocr_status,
        )

        if result.decision == ReviewDecision.MANUAL_REVIEW_REQUIRED:
            await self.review_required(job_id, ocr_confidence)

        return result
