"""Deal Health Snapshot — операционное здоровье сделки."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin

class DealHealthSnapshot(UUIDMixin, Base):
    __tablename__ = "deal_health_snapshots"

    deal_id = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    score = mapped_column(Float, nullable=False, default=0.0)
    compliance_score = mapped_column(Float, nullable=False, default=0.0)
    risk_score = mapped_column(Float, nullable=False, default=0.0)
    sla_score = mapped_column(Float, nullable=False, default=100.0)
    document_score = mapped_column(Float, nullable=False, default=0.0)
    activity_score = mapped_column(Float, nullable=False, default=100.0)
    calculated_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)