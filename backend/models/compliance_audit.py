"""Compliance Audit — доказательная база compliance/risk/workflow проверок."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, UUIDMixin


class ComplianceAudit(UUIDMixin, Base):
    __tablename__ = "compliance_audits"

    deal_id: Mapped[UUID] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    audit_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # compliance | risk | workflow
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    blocking_issues: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    used_regulations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    used_documents: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
