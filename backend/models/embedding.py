from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base
from backend.models.base import UUIDMixin


class Embedding(UUIDMixin, Base):
    __tablename__ = "embeddings"
    __allow_unmapped__ = True

    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    chunk_id: Mapped[UUID | None] = mapped_column(nullable=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding: Mapped = mapped_column(Vector(384), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True, default=None)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())