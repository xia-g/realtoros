"""Agent Tool Call — audit log for every tool executed by Agent Runtime."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, UUIDMixin


class AgentToolCall(UUIDMixin, Base):
    """Аудит вызова инструмента агентом."""

    __tablename__ = "agent_tool_calls"

    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[UUID | None] = mapped_column(ForeignKey("knowledge_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
