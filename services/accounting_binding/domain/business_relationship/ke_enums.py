"""
Knowledge Evolution enums: EventType, TrustLevel, AuthorityLevel, ConflictType.

All immutable. No logic. No evaluation.
"""
from __future__ import annotations

from enum import Enum


class KnowledgeEventType(str, Enum):
    """Тип события знания. Только описание."""
    CREATED = "created"
    UPDATED = "updated"
    SUPERSEDED = "superseded"
    TERMINATED = "terminated"
    MERGED = "merged"
    SPLIT = "split"
    CONFLICT_DETECTED = "conflict_detected"
    CONFLICT_RESOLVED = "conflict_resolved"
    TRUST_CHANGED = "trust_changed"
    AUTHORITY_CHANGED = "authority_changed"


class TrustLevel(str, Enum):
    """Уровень доверия. Без вычислений."""
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERIFIED = "verified"


class AuthorityLevel(str, Enum):
    """Уровень авторитетности источника. Без оценки."""
    UNKNOWN = "unknown"
    WEAK = "weak"
    NORMAL = "normal"
    STRONG = "strong"
    OFFICIAL = "official"


class ConflictType(str, Enum):
    """Тип конфликта. Без разрешения."""
    IDENTITY = "identity"
    OWNERSHIP = "ownership"
    PARTICIPANT = "participant"
    PERIOD = "period"
    VALUE = "value"
    RELATIONSHIP = "relationship"
    OTHER = "other"
