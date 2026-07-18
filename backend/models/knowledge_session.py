"""Knowledge Session — conversational memory for Knowledge Agent.

SECURITY: Every query MUST be filtered by user_id.
NEVER trust session_id alone (Review Gate C3).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.models.base import UUIDMixin, TimestampMixin


class KnowledgeSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sessions"

    user_id: Mapped[UUID] = mapped_column(PUUID(as_uuid=True), nullable=False, index=True)
    tenant_id: Mapped[UUID | None] = mapped_column(PUUID(as_uuid=True), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    correlation_id: Mapped[UUID | None] = mapped_column(PUUID(as_uuid=True), nullable=True)

    # Relationship
    messages: Mapped[list[KnowledgeMessage]] = relationship(
        "KnowledgeMessage", back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class KnowledgeMessage(UUIDMixin, Base):
    __tablename__ = "knowledge_messages"

    session_id: Mapped[UUID] = mapped_column(
        PUUID(as_uuid=True),
        ForeignKey("knowledge_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(nullable=False)
    token_count: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    correlation_id: Mapped[UUID | None] = mapped_column(PUUID(as_uuid=True), nullable=True)

    # Relationship
    session: Mapped[KnowledgeSession] = relationship(
        "KnowledgeSession", back_populates="messages",
    )
