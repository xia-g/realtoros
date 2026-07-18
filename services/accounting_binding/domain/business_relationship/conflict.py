"""
Conflict Model — detect and track knowledge conflicts.

When two sources disagree about the same fact, the conflict is recorded.
Both values are preserved. Resolution chooses one, the other is archived.

Status: OPEN → RESOLVED / IGNORED
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ConflictStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    IGNORED = "ignored"


@dataclass
class ConflictCandidate:
    """One side of a conflict."""
    value: str
    authority: str = "normal"     # AuthorityLevel value
    trust: str = "unknown"         # TrustLevel value
    source_document_id: str = ""


@dataclass
class KnowledgeConflict:
    """Конфликт между версиями одного факта."""
    entity_id: str
    field_name: str                      # area, owner, address, etc.
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    candidates: list[ConflictCandidate] = field(default_factory=list)
    status: ConflictStatus = ConflictStatus.OPEN
    detected_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None
    resolved_to: str | None = None       # which value was chosen

    @property
    def is_open(self) -> bool:
        return self.status == ConflictStatus.OPEN

    def resolve(self, chosen_value: str):
        self.status = ConflictStatus.RESOLVED
        self.resolved_to = chosen_value
        self.resolved_at = datetime.utcnow()

    def ignore(self):
        self.status = ConflictStatus.IGNORED

    def add_candidate(self, value: str, authority: str = "normal",
                      trust: str = "unknown", doc_id: str = ""):
        """Add another conflicting value."""
        if not any(c.value == value for c in self.candidates):
            self.candidates.append(ConflictCandidate(
                value=value, authority=authority,
                trust=trust, source_document_id=doc_id,
            ))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "field_name": self.field_name,
            "status": self.status.value,
            "candidates": [
                {"value": c.value, "authority": c.authority, "trust": c.trust}
                for c in self.candidates
            ],
            "detected_at": self.detected_at.isoformat(),
            "resolved_to": self.resolved_to,
        }


class ConflictDetector:
    """Выявляет конфликты между версиями фактов."""

    @staticmethod
    def detect(entity_id: str, field: str, old_value: str | None,
               new_value: str, authority_level: str = "normal") -> KnowledgeConflict | None:
        """Сравнить старое и новое значение. Если отличаются — конфликт."""
        if not old_value or old_value == new_value:
            return None

        conflict = KnowledgeConflict(
            entity_id=entity_id,
            field_name=field,
        )
        conflict.add_candidate(old_value, authority=authority_level)
        conflict.add_candidate(new_value, authority=authority_level)
        return conflict

    @staticmethod
    def resolve_by_authority(conflict: KnowledgeConflict) -> str | None:
        """Автоматическое разрешение по авторитетности."""
        if not conflict.candidates:
            return None
        # Sort by authority weight (highest first)
        weights = {
            "official": 1.0, "high": 0.75, "normal": 0.5,
            "low": 0.25, "very_low": 0.1,
        }
        ranked = sorted(conflict.candidates,
                        key=lambda c: weights.get(c.authority.lower(), 0.1),
                        reverse=True)
        best = ranked[0]
        # Auto-resolve if highest authority is OFFICIAL or HIGH and others are lower
        if best.authority in ("official", "high") and all(
            c.authority != best.authority or c.value == best.value
            for c in conflict.candidates
        ):
            return best.value
        return None
