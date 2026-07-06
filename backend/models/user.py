from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.models.base import UUIDMixin, TimestampMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    role_id = mapped_column(ForeignKey("roles.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(500), nullable=True)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    role: Mapped["Role"] = relationship("Role", back_populates="users")  # noqa: F821
    deals_created: Mapped[list["Deal"]] = relationship("Deal", back_populates="creator", foreign_keys="Deal.created_by")  # noqa: F821
    communications_created: Mapped[list["Communication"]] = relationship("Communication", back_populates="creator", foreign_keys="Communication.created_by")  # noqa: F821
    communications_assigned: Mapped[list["Communication"]] = relationship("Communication", back_populates="assignee", foreign_keys="Communication.assigned_to")  # noqa: F821
    documents_uploaded: Mapped[list["Document"]] = relationship("Document", back_populates="uploader")  # noqa: F821
    tasks_created: Mapped[list["Task"]] = relationship("Task", back_populates="creator", foreign_keys="Task.created_by")  # noqa: F821
    tasks_assigned: Mapped[list["Task"]] = relationship("Task", back_populates="assignee", foreign_keys="Task.assigned_to")  # noqa: F821
    tasks_completed: Mapped[list["Task"]] = relationship("Task", back_populates="completer", foreign_keys="Task.completed_by")  # noqa: F821
