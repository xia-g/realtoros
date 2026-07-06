"""Stakeholder — внешний участник сделки."""

from __future__ import annotations

from uuid import UUID
from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, TimestampMixin, UUIDMixin

class Stakeholder(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "stakeholders"

    deal_id = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    stakeholder_type = mapped_column(String(30), nullable=False, index=True)
    name = mapped_column(String(255), nullable=False)
    organization = mapped_column(String(255), nullable=True)
    contact_info = mapped_column(JSONB, nullable=True)
    responsibilities = mapped_column(JSONB, nullable=True)
    status = mapped_column(String(20), nullable=False, default="pending")
    is_blocking = mapped_column(Boolean, default=False, nullable=False)