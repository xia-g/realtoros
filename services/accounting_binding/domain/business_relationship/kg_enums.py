"""
GraphNodeType, GraphEdgeType — node and edge type enums.

NO logic. Pure enumeration.
"""
from __future__ import annotations

from enum import Enum


class GraphNodeType(str, Enum):
    """Тип узла графа. Без логики."""
    ENTITY = "entity"
    PROPERTY = "property"
    AGREEMENT = "agreement"
    DOCUMENT = "document"
    DEAL = "deal"
    EVENT = "event"
    FACT = "fact"
    ORGANIZATION = "organization"
    PERSON = "person"


class GraphEdgeType(str, Enum):
    """Тип ребра графа. Без логики."""
    HAS_FACT = "has_fact"
    HAS_AGREEMENT = "has_agreement"
    OWNS = "owns"
    PARTICIPATES = "participates"
    REFERENCES = "references"
    SUPERSEDES = "supersedes"
    DERIVED_FROM = "derived_from"
    RELATED_TO = "related_to"
    LOCATED_AT = "located_at"
    BELONGS_TO = "belongs_to"
