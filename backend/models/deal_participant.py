from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.models.base import UUIDMixin, TimestampMixin


class DealParticipant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deal_participants"

    deal_id = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=False)
    client_id = mapped_column(ForeignKey("clients.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    deal: Mapped["Deal"] = relationship("Deal", back_populates="participants")  # noqa: F821
    client: Mapped["Client"] = relationship("Client", back_populates="deal_participations")  # noqa: F821
