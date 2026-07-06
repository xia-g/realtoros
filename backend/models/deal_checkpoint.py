"""Deal Checkpoint — этапы сделки."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin, UUIDMixin


class DealCheckpoint(UUIDMixin, TimestampMixin, Base):
    """Чекпоинт сделки — обязательный этап в жизненном цикле."""

    __tablename__ = "deal_checkpoints"

    deal_id: Mapped[UUID] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)  # NEW, PREPARATION, SIGNING, REGISTRATION, CLOSED
    checkpoint_key: Mapped[str] = mapped_column(String(100), nullable=False)  # client_verified, agreement_draft, ...
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    deal: Mapped["Deal"] = relationship("Deal", back_populates="checkpoints")
    completer: Mapped["User | None"] = relationship("User", foreign_keys=[completed_by])

    __table_args__ = (
        UniqueConstraint("deal_id", "checkpoint_key", name="uq_deal_checkpoint_key"),
    )
