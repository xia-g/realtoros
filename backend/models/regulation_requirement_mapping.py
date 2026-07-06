"""Regulation Requirement Mapping — связь regulation ↔ checkpoint ↔ document."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin, UUIDMixin


class RegulationRequirementMapping(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "regulation_requirement_mappings"

    regulation_id: Mapped[UUID] = mapped_column(ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    checkpoint_key: Mapped[str] = mapped_column(String(100), nullable=False)
    article: Mapped[str | None] = mapped_column(String(100), nullable=True)  # статья закона
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("regulation_id", "document_type", "checkpoint_key", name="uq_reg_requirement_mapping"),
    )
