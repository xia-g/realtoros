from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.models.base import UUIDMixin, TimestampMixin


class Communication(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "communications"

    communication_type: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    client_id = mapped_column(ForeignKey("clients.id"), nullable=True)
    deal_id = mapped_column(ForeignKey("deals.id"), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assigned_to = mapped_column(ForeignKey("users.id"), nullable=True)
    is_important: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list, nullable=True)
    created_by = mapped_column(ForeignKey("users.id"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    client: Mapped["Client | None"] = relationship("Client", back_populates="communications", foreign_keys=[client_id])  # noqa: F821
    deal: Mapped["Deal | None"] = relationship("Deal", back_populates="communications", foreign_keys=[deal_id])  # noqa: F821
    creator: Mapped["User"] = relationship("User", back_populates="communications_created", foreign_keys=[created_by])  # noqa: F821
    assignee: Mapped["User | None"] = relationship("User", back_populates="communications_assigned", foreign_keys=[assigned_to])  # noqa: F821
