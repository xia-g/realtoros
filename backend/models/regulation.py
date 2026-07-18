"""Regulation — нормативный акт из официальных источников."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, UUIDMixin


class Regulation(UUIDMixin, TimestampMixin, Base):
    """Нормативный акт. Источник: Минфин, ФНС, Росреестр, Госуслуги, ЦБ."""

    __tablename__ = "regulations"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    trust_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="OFFICIAL",
        index=True,
    )
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    regulation_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="law",
    )

    __table_args__ = (
        UniqueConstraint("source", "hash", name="uq_regulation_source_hash"),
    )
