"""
PropertyReference — typed reference to a Projection field.

DSL never uses raw string paths. All references are typed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from query.query_target import QueryTarget

# Allowed properties per target type
PROPERTY_REGISTRY: dict[QueryTarget, dict[str, type]] = {
    QueryTarget.ENTITY: {
        "id": str,
        "name": str,
        "type": str,
        "identifiers": list,
        "created_at": str,
    },
    QueryTarget.AGREEMENT: {
        "id": str,
        "type": str,
        "status": str,
        "party_names": list,
        "period_start": str,
        "period_end": str,
        "created_at": str,
    },
    QueryTarget.OWNERSHIP: {
        "id": str,
        "entity_id": str,
        "property_id": str,
        "share": float,
        "registered_at": str,
    },
    QueryTarget.TIMELINE: {
        "id": str,
        "entity_id": str,
        "event_type": str,
        "event_date": str,
        "description": str,
    },
    QueryTarget.GRAPH: {
        "id": str,
        "node_id": str,
        "edge_type": str,
        "source_id": str,
        "target_id": str,
        "depth": int,
    },
    QueryTarget.RISK: {
        "id": str,
        "entity_id": str,
        "risk_type": str,
        "score": float,
        "description": str,
        "created_at": str,
    },
    QueryTarget.PROVENANCE: {
        "id": str,
        "node_id": str,
        "source_type": str,
        "source_description": str,
        "confidence": float,
    },
}


@dataclass(frozen=True)
class PropertyReference:
    """Типизированная ссылка на поле Projection.

    Никаких строковых путей. Все ссылки типизированы.
    """
    target: QueryTarget
    property_name: str

    def __post_init__(self) -> None:
        if self.property_name not in PROPERTY_REGISTRY.get(self.target, {}):
            valid = list(PROPERTY_REGISTRY.get(self.target, {}).keys())
            raise ValueError(
                f"Unknown property '{self.property_name}' for {self.target.name}. "
                f"Valid: {valid}"
            )

    @property
    def property_type(self) -> type:
        """Возвращает тип свойства."""
        return PROPERTY_REGISTRY[self.target][self.property_name]
