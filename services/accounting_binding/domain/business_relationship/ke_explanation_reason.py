"""
ExplanationReasonType — types of reasoning for an explanation.

Pure enum. No logic.
"""
from __future__ import annotations

from enum import Enum


class ExplanationReasonType(str, Enum):
    """Тип обоснования объяснения. Без логики."""
    FACT_MATCH = "fact_match"
    AGREEMENT_MATCH = "agreement_match"
    IDENTITY_MATCH = "identity_match"
    GRAPH_RELATION = "graph_relation"
    KNOWLEDGE_EVENT = "knowledge_event"
    AUTHORITY = "authority"
    TRUST = "trust"
    CONFLICT = "conflict"
    DERIVED = "derived"
    MANUAL = "manual"
