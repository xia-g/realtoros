"""Analytics Alert — operational alerts for business intelligence."""

from __future__ import annotations

from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin

class AnalyticsAlert(UUIDMixin, Base):
    __tablename__ = "analytics_alerts"

    severity = mapped_column(String(10), nullable=False, index=True)
    alert_type = mapped_column(String(50), nullable=False, index=True)
    title = mapped_column(String(255), nullable=False)
    description = mapped_column(Text, nullable=True)
    payload = mapped_column(JSONB, nullable=True)
    status = mapped_column(String(20), nullable=False, default="open")
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    resolved_at = mapped_column(DateTime(timezone=True), nullable=True)