"""
KnowledgeChange — describes a change to a single knowledge field.

Immutable. NO application of changes. Just description.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class KnowledgeChange:
    """Изменение одного поля знания. Immutable."""
    field: str
    old_value: Any = None
    new_value: Any = None
