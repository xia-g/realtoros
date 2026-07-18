"""Deal Risk Assessment — движок оценки рисков сделки."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin, UUIDMixin


class DealRiskAssessment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deal_risk_assessments"

    deal_id: Mapped[UUID] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="LOW")
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    factors: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    score_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=True)
    recommendations: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    assessed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    deal: Mapped["Deal"] = relationship("Deal")  # noqa: F821
