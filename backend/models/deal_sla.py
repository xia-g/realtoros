"""Deal SLA — операционные дедлайны сделки."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, TimestampMixin, UUIDMixin

class DealSLA(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deal_slas"

    deal_id = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_key = mapped_column(String(50), nullable=False, index=True)
    sla_type = mapped_column(String(30), nullable=False, default="stage")
    due_date = mapped_column(Date, nullable=False)
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)
    status = mapped_column(String(20), nullable=False, default="pending")
    notes = mapped_column(Text, nullable=True)