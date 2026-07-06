"""Regulation Source — внешний провайдер нормативных актов."""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, TimestampMixin, UUIDMixin

class RegulationSource(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "regulation_sources"

    code = mapped_column(String(50), unique=True, nullable=False, index=True)
    name = mapped_column(String(255), nullable=False)
    source_type = mapped_column(String(50), nullable=False, index=True)
    base_url = mapped_column(String(500), nullable=True)
    trust_level = mapped_column(String(20), nullable=False, default="OFFICIAL")
    enabled = mapped_column(Boolean, default=True, nullable=False)
    sync_frequency_hours = mapped_column(Integer, default=24, nullable=False)