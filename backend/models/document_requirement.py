"""Document Requirement — обязательные документы для типа сделки."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin, UUIDMixin


class DocumentRequirement(UUIDMixin, TimestampMixin, Base):
    """Требование к документу для определённого типа сделки."""

    __tablename__ = "document_requirements"

    deal_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # SALE_APARTMENT, MORTGAGE, ...
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    regulation_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)  # ссылка на нормативный акт
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("deal_type", "document_type", name="uq_deal_type_doc_type"),
    )
