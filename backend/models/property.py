from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.models.base import UUIDMixin, TimestampMixin


class Property(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "properties"

    property_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="available", nullable=False)
    deal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    area_total: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    area_living: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    rooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floors_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    price_currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    price_per_meter: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    commission: Mapped[float | None] = mapped_column(Numeric(15, 2), default=0, nullable=True)
    owner_id = mapped_column(ForeignKey("clients.id"), nullable=True)
    photos: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list, nullable=True)
    documents: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    owner: Mapped["Client"] = relationship("Client", back_populates="properties")  # noqa: F821
    deals: Mapped[list["Deal"]] = relationship("Deal", back_populates="property")  # noqa: F821
    property_documents: Mapped[list["Document"]] = relationship("Document", back_populates="property")  # noqa: F821
    property_tasks: Mapped[list["Task"]] = relationship("Task", back_populates="property")  # noqa: F821
