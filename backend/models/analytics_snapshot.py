"""Analytics Snapshot — point-in-time analytical data."""

from __future__ import annotations

from datetime import date, datetime
from sqlalchemy import Date, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin

class AnalyticsSnapshot(UUIDMixin, Base):
    __tablename__ = "analytics_snapshots"

    snapshot_type = mapped_column(String(50), nullable=False, index=True)
    snapshot_date = mapped_column(Date, nullable=False, index=True)
    payload = mapped_column(JSONB, nullable=False)
    correlation_id = mapped_column(String(64), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)