from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.models.base import UUIDMixin, TimestampMixin


class Client(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "clients"

    type: Mapped[str] = mapped_column(String(20), default="buyer", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="lead", nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="other", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list, nullable=True)
    created_by = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    contacts: Mapped[list["ClientContact"]] = relationship("ClientContact", back_populates="client", cascade="all, delete-orphan")  # noqa: F821
    properties: Mapped[list["Property"]] = relationship("Property", back_populates="owner")  # noqa: F821
    deal_participations: Mapped[list["DealParticipant"]] = relationship("DealParticipant", back_populates="client")  # noqa: F821
    communications: Mapped[list["Communication"]] = relationship("Communication", back_populates="client")  # noqa: F821
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="client")  # noqa: F821
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="client")  # noqa: F821
