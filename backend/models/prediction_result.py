"""Prediction Result — scores from predictive intelligence engine."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin

class PredictionResult(UUIDMixin, Base):
    __tablename__ = "prediction_results"

    prediction_type = mapped_column(String(50), nullable=False, index=True)
    entity_type = mapped_column(String(30), nullable=False, index=True)
    entity_id = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    score = mapped_column(Float, nullable=False, default=0.0)
    confidence = mapped_column(Float, nullable=False, default=0.0)
    explanation = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)