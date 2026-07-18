"""Deal Document Package — система контроля комплектности документов сделки."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin, UUIDMixin


class DealDocumentPackage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deal_document_packages"

    deal_id: Mapped[UUID] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_id: Mapped[UUID] = mapped_column(ForeignKey("document_requirements.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="missing")
    attached_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    attached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    verified_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    deal: Mapped["Deal"] = relationship("Deal")  # noqa: F821
    requirement: Mapped["DocumentRequirement"] = relationship("DocumentRequirement")  # noqa: F821
    document: Mapped["Document | None"] = relationship("Document")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("deal_id", "requirement_id", name="uq_deal_doc_requirement"),
    )
