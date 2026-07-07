"""
AgreementStatus — lifecycle state of an Agreement.

Architecture Freeze: ACTIVE, SUPERSEDED, HISTORICAL.
"""
from __future__ import annotations

from enum import Enum


class AgreementStatus(str, Enum):
    """Статус жизненного цикла соглашения."""
    ACTIVE = "active"             # действующее соглашение
    SUPERSEDED = "superseded"     # заменено новым соглашением
    HISTORICAL = "historical"     # архивное, неактивное
    TERMINATED = "terminated"     # расторгнуто
    DRAFT = "draft"               # черновик
