from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.models.base import UUIDMixin, TimestampMixin


class Lead(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "leads"

    source: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_metadata: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)

    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(100), nullable=True)

    interest_type: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    property_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    budget_min: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    budget_max: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    locations: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="new", nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    score: Mapped[float | None] = mapped_column(Float, default=0.0, nullable=True)
    score_components: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)
    score_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    priority: Mapped[str | None] = mapped_column(String(10), default="cold", nullable=True)
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assigned_to = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_auto_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    qualified_by = mapped_column(ForeignKey("users.id"), nullable=True)
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    qualification_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    client_id = mapped_column(ForeignKey("clients.id"), nullable=True)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deal_id = mapped_column(ForeignKey("deals.id"), nullable=True)

    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by = mapped_column(ForeignKey("users.id"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
