from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import Date, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base
from backend.models.base import UUIDMixin


class BudgetUsage(UUIDMixin, Base):
    __tablename__ = "budget_usage"

    tenant_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    user_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    spent_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)