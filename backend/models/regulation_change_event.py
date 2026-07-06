"""Regulation Change Event — обнаруженные изменения в нормативных актах."""

from __future__ import annotations

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin

class RegulationChangeEvent(UUIDMixin, Base):
    __tablename__ = "regulation_change_events"

    regulation_id = mapped_column(ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False, index=True)
    version_from = mapped_column(String(20), nullable=True)
    version_to = mapped_column(String(20), nullable=False)
    change_type = mapped_column(String(20), nullable=False, index=True)
    summary = mapped_column(Text, nullable=False)
    impact_level = mapped_column(String(20), nullable=False, default="medium")
    detected_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)