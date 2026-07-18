"""Regulation Impact — AI-анализ изменений нормативных актов."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin, UUIDMixin


class RegulationImpact(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "regulation_impacts"

    version_id: Mapped[UUID] = mapped_column(ForeignKey("regulation_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    affected_deals_count: Mapped[int] = mapped_column(default=0, nullable=False)
    affected_templates_count: Mapped[int] = mapped_column(default=0, nullable=False)
    affected_workflows_count: Mapped[int] = mapped_column(default=0, nullable=False)
    affected_requirements_count: Mapped[int] = mapped_column(default=0, nullable=False)
    affected_deal_ids: Mapped[list[UUID] | None] = mapped_column(JSONB, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    recommendations: Mapped[str | None] = mapped_column(Text, nullable=True)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    version: Mapped["RegulationVersion"] = relationship("RegulationVersion")  # noqa: F821
