"""Regulation Sync Log — история синхронизации."""

from __future__ import annotations

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin

class RegulationSyncLog(UUIDMixin, Base):
    __tablename__ = "regulation_sync_logs"

    source_id = mapped_column(ForeignKey("regulation_sources.id", ondelete="SET NULL"), nullable=True, index=True)
    status = mapped_column(String(20), nullable=False, default="pending")
    started_at = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)
    documents_found = mapped_column(Integer, default=0, nullable=False)
    regulations_created = mapped_column(Integer, default=0, nullable=False)
    regulations_updated = mapped_column(Integer, default=0, nullable=False)
    errors_count = mapped_column(Integer, default=0, nullable=False)
    error_message = mapped_column(Text, nullable=True)