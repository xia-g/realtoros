"""Deal Timeline — хронологическая история сделки."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin

class DealTimelineEvent(UUIDMixin, Base):
    __tablename__ = "deal_timeline_events"

    deal_id = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = mapped_column(String(50), nullable=False, index=True)
    source_component = mapped_column(String(50), nullable=False)
    actor_id = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    title = mapped_column(String(255), nullable=False)
    description = mapped_column(Text, nullable=True)
    meta = mapped_column("metadata", JSONB, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)