"""Deterministic entity selection — top-3 unique (type, id) by score."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from backend.services.knowledge.context.contracts import MAX_ENTITIES


@dataclass
class EntityRef:
    entity_type: str
    entity_id: UUID
    score: float


def select_entities(search_results: list, max_entities: int = MAX_ENTITIES) -> list[EntityRef]:
    """Select top-N unique entities by (type, id) with deterministic sort."""
    seen: dict[tuple[str, str], float] = {}

    for r in search_results:
        etype = getattr(r, "entity_type", None) or r.get("entity_type", "")
        eid = getattr(r, "entity_id", None) or r.get("entity_id", "")
        score = getattr(r, "score", None) or r.get("score", 0.0)

        if not etype or not eid:
            continue

        key = (str(etype), str(eid))
        if key not in seen or score > seen[key]:
            seen[key] = score

    sorted_items = sorted(
        seen.items(),
        key=lambda x: (-x[1], x[0][0], x[0][1]),
    )

    return [
        EntityRef(entity_type=t, entity_id=UUID(i), score=s)
        for (t, i), s in sorted_items[:max_entities]
    ]