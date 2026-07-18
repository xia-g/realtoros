"""
QueryTarget — describes which Projection type the query targets.

Immutable enum. DSL knows only the Projection type, never the Store.
"""
from __future__ import annotations

from enum import Enum, auto


class QueryTarget(Enum):
    """Тип Projection, к которому обращён запрос.

    DSL знает только тип Projection. Не знает Store.
    """
    ENTITY = auto()
    AGREEMENT = auto()
    OWNERSHIP = auto()
    TIMELINE = auto()
    GRAPH = auto()
    RISK = auto()
    PROVENANCE = auto()
