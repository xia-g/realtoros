"""
OCR Review State — отдельный lifecycle для ревью OCR.

НЕ смешивать с process_state или document_status.

OCRReviewState:
  NOT_REQUIRED — OCR completed, pipeline идёт сразу
  REQUIRED — OCR need_review, требуется human review
  APPROVED — human approved OCR результат
  REJECTED — human rejected OCR результат
"""
from __future__ import annotations

from enum import Enum


class OCRReviewState(str, Enum):
    """Состояние ревью OCR результата."""
    NOT_REQUIRED = "not_required"  # OCR completed — пропускаем review
    REQUIRED = "required"          # OCR need_review — ждём human review
    APPROVED = "approved"          # Человек подтвердил OCR
    REJECTED = "rejected"          # Человек отклонил OCR


# Маппинг OCR статусов в review_state
OCR_STATUS_MAP: dict[str, OCRReviewState] = {
    "completed": OCRReviewState.NOT_REQUIRED,
    "need_review": OCRReviewState.REQUIRED,
    "failed": OCRReviewState.REJECTED,
}
