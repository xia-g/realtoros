"""SQLAlchemy model for consumer_processed_events table.

Tracks which events each consumer has already processed.
Enables idempotent processing: same event_id delivered twice -> processed once.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class ConsumerProcessedEvent(Base):
    __tablename__ = "consumer_processed_events"

    consumer_name: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
