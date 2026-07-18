"""
ExplainabilityRequest — describes required explainability level.

DSL only describes the requirement. Engine fulfills it.
"""
from __future__ import annotations

from enum import Enum, auto


class ExplainabilityLevel(Enum):
    """Уровень Explainability, требуемый в запросе.

    DSL только описывает требование.
    Получение Explainability относится к Query Engine.
    """
    NONE = auto()
    SUMMARY = auto()
    FULL = auto()
