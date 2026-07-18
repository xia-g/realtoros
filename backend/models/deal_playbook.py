"""Deal Playbook — формализованные операционные процессы по типу сделки."""

from __future__ import annotations

from uuid import UUID
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base, TimestampMixin, UUIDMixin

class DealPlaybook(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deal_playbooks"

    code = mapped_column(String(50), unique=True, nullable=False, index=True)
    name = mapped_column(String(255), nullable=False)
    deal_type = mapped_column(String(50), nullable=False, index=True)
    version = mapped_column(String(20), nullable=False, default="1.0")
    is_active = mapped_column(Boolean, default=True, nullable=False)
    description = mapped_column(Text, nullable=True)
    stages = relationship("DealPlaybookStage", back_populates="playbook", cascade="all, delete-orphan", order_by="DealPlaybookStage.sequence")

class DealPlaybookStage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deal_playbook_stages"

    playbook_id = mapped_column(ForeignKey("deal_playbooks.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_key = mapped_column(String(50), nullable=False)
    name = mapped_column(String(255), nullable=False)
    sequence = mapped_column(Integer, nullable=False, default=0)
    sla_days = mapped_column(Integer, nullable=True)
    is_required = mapped_column(Boolean, default=True, nullable=False)
    playbook = relationship("DealPlaybook", back_populates="stages")
    checkpoints = relationship("DealPlaybookCheckpoint", back_populates="stage", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("playbook_id", "stage_key", name="uq_playbook_stage"),)

class DealPlaybookCheckpoint(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deal_playbook_checkpoints"

    stage_id = mapped_column(ForeignKey("deal_playbook_stages.id", ondelete="CASCADE"), nullable=False, index=True)
    checkpoint_key = mapped_column(String(100), nullable=False)
    title = mapped_column(String(255), nullable=False)
    description = mapped_column(Text, nullable=True)
    required = mapped_column(Boolean, default=True, nullable=False)
    regulation_id = mapped_column(ForeignKey("regulations.id", ondelete="SET NULL"), nullable=True)
    stage = relationship("DealPlaybookStage", back_populates="checkpoints")