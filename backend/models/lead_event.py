from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base
from backend.models.base import UUIDMixin


class LeadEvent(UUIDMixin, Base):
    __tablename__ = "lead_events"

    # ── Lead reference (child history — cascade with parent) ──
    lead_id = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)

    # ── Status change tracking ──
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ── Priority change tracking ──
    from_priority: Mapped[str | None] = mapped_column(String(10), nullable=True)
    to_priority: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # ── Score change tracking ──
    from_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    to_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ── Assignment change tracking ──
    from_user_id = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    to_user_id = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    # ── Audit fields ──
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    # ── Extensible metadata ──
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict, nullable=True)

    # ── Timestamp with DB-side default — survives raw SQL inserts ──
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(),
    )
