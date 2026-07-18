"""Deal Workflow — управляемый жизненный цикл сделки."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin, UUIDMixin


class DealWorkflow(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deal_workflows"

    deal_id: Mapped[UUID] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_type: Mapped[str] = mapped_column(String(50), nullable=False, default="SALE_APARTMENT")
    current_stage: Mapped[str] = mapped_column(String(50), nullable=False, default="LEAD")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    deal: Mapped["Deal"] = relationship("Deal", back_populates="workflows")  # noqa: F821
    transitions: Mapped[list["DealStageTransition"]] = relationship("DealStageTransition", back_populates="workflow", cascade="all, delete-orphan")  # noqa: F821


class DealStageTransition(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deal_stage_transitions"

    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("deal_workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    from_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    to_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    transitioned_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    conditions_met: Mapped[bool] = mapped_column(default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    workflow: Mapped["DealWorkflow"] = relationship("DealWorkflow", back_populates="transitions")  # noqa: F821