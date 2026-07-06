from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.models.base import UUIDMixin, TimestampMixin


class Document(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    document_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    client_id = mapped_column(ForeignKey("clients.id"), nullable=True)
    property_id = mapped_column(ForeignKey("properties.id"), nullable=True)
    deal_id = mapped_column(ForeignKey("deals.id"), nullable=True)
    uploaded_by = mapped_column(ForeignKey("users.id"), nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    client: Mapped["Client | None"] = relationship("Client", back_populates="documents", foreign_keys=[client_id])  # noqa: F821
    property: Mapped["Property | None"] = relationship("Property", back_populates="property_documents", foreign_keys=[property_id])  # noqa: F821
    deal: Mapped["Deal | None"] = relationship("Deal", back_populates="documents", foreign_keys=[deal_id])  # noqa: F821
    uploader: Mapped["User"] = relationship("User", back_populates="documents_uploaded")  # noqa: F821
