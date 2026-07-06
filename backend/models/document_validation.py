"""Document Validation — проверка операционной готовности документов."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin

class DocumentValidation(UUIDMixin, Base):
    __tablename__ = "document_validations"

    document_id = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    validation_status = mapped_column(String(20), nullable=False, default="pending")
    validation_score = mapped_column(Float, nullable=False, default=0.0)
    issues = mapped_column(JSONB, nullable=True)
    validated_at = mapped_column(DateTime(timezone=True), nullable=True)