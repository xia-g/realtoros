"""SQLAlchemy model for resolution_attempt table.

Tracks all resolution decisions (RESOLVED / AMBIGUOUS / NOT_FOUND)
for audit trail and manual review workflow.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class ResolutionAttempt(Base):
    __tablename__ = "resolution_attempt"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deals.id"),
        nullable=False,
    )
    resolver_type: Mapped[str] = mapped_column(String(20), nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)
    resolved_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    candidate_ids: Mapped[list] = mapped_column(
        JSONB, default=list
    )
    document_payload_snapshot: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
