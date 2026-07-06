from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.models.base import UUIDMixin, TimestampMixin


class Deal(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deals"

    deal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="negotiation", nullable=False)
    property_id = mapped_column(ForeignKey("properties.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    price_currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    commission: Mapped[float | None] = mapped_column(Numeric(15, 2), default=0, nullable=True)
    commission_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    deposit_amount: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    closing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="other", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by = mapped_column(ForeignKey("users.id"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    property: Mapped["Property"] = relationship("Property", back_populates="deals")  # noqa: F821
    participants: Mapped[list["DealParticipant"]] = relationship("DealParticipant", back_populates="deal", cascade="all, delete-orphan")  # noqa: F821
    creator: Mapped["User"] = relationship("User", back_populates="deals_created", foreign_keys=[created_by])  # noqa: F821
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="deal")  # noqa: F821
    communications: Mapped[list["Communication"]] = relationship("Communication", back_populates="deal")  # noqa: F821
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="deal")  # noqa: F821
    checkpoints: Mapped[list["DealCheckpoint"]] = relationship("DealCheckpoint", back_populates="deal", cascade="all, delete-orphan")  # noqa: F821
