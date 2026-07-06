from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.models.base import UUIDMixin, TimestampMixin


class Task(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    task_type: Mapped[str] = mapped_column(String(20), default="other", nullable=False)
    client_id = mapped_column(ForeignKey("clients.id"), nullable=True)
    deal_id = mapped_column(ForeignKey("deals.id"), nullable=True)
    property_id = mapped_column(ForeignKey("properties.id"), nullable=True)
    assigned_to = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by = mapped_column(ForeignKey("users.id"), nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by = mapped_column(ForeignKey("users.id"), nullable=True)
    reminder: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    client: Mapped["Client | None"] = relationship("Client", back_populates="tasks", foreign_keys=[client_id])  # noqa: F821
    deal: Mapped["Deal | None"] = relationship("Deal", back_populates="tasks", foreign_keys=[deal_id])  # noqa: F821
    property: Mapped["Property | None"] = relationship("Property", back_populates="property_tasks", foreign_keys=[property_id])  # noqa: F821
    assignee: Mapped["User | None"] = relationship("User", back_populates="tasks_assigned", foreign_keys=[assigned_to])  # noqa: F821
    creator: Mapped["User"] = relationship("User", back_populates="tasks_created", foreign_keys=[created_by])  # noqa: F821
    completer: Mapped["User | None"] = relationship("User", back_populates="tasks_completed", foreign_keys=[completed_by])  # noqa: F821
