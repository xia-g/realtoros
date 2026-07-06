"""Deal Operations Audit — журнал операционных изменений."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin

class DealOperationsAudit(UUIDMixin, Base):
    __tablename__ = "deal_operations_audits"

    deal_id = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    operation_type = mapped_column(String(50), nullable=False, index=True)
    old_value = mapped_column(Text, nullable=True)
    new_value = mapped_column(Text, nullable=True)
    actor_id = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    correlation_id = mapped_column(String(64), nullable=False, index=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)