"""Deal Action — операционные действия по сделке."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, TimestampMixin, UUIDMixin

class DealAction(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deal_actions"

    deal_id = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = mapped_column(String(50), nullable=False, index=True)
    title = mapped_column(String(255), nullable=False)
    description = mapped_column(Text, nullable=True)
    assigned_to = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    due_date = mapped_column(DateTime(timezone=True), nullable=True)
    priority = mapped_column(String(10), nullable=False, default="medium")
    status = mapped_column(String(20), nullable=False, default="pending")
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)