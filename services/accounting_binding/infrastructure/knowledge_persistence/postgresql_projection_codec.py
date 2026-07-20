"""
v2.3 — PostgreSQL Projection serialisation codec.

Converts Projection (frozen dataclass) ↔ JSON-friendly dict for JSONB storage.
Supports all 4 materialized projection types:
  - _EntityProjection (ENTITY)
  - _AgreementProjection (AGREEMENT)
  - _GraphProjection (GRAPH)
  - _ProvenanceProjection (PROVENANCE)

NOT part of Domain. Infrastructure only.
"""
from __future__ import annotations

from dataclasses import fields as dc_fields, is_dataclass
from typing import Any

from projection.projection import Projection, ProjectionId, ProjectionType
from projection.projection_digest import ProjectionDigest

# Import the concrete projection DTOs from materialization module
from application.knowledge_persistence.materialization import (
    _EntityProjection,
    _AgreementProjection,
    _GraphProjection,
    _ProvenanceProjection,
)


# ── Registry: ProjectionType → concrete class ────────────────────

PROJECTION_CLASSES: dict[ProjectionType, type] = {
    ProjectionType.ENTITY: _EntityProjection,
    ProjectionType.AGREEMENT: _AgreementProjection,
    ProjectionType.GRAPH: _GraphProjection,
    ProjectionType.PROVENANCE: _ProvenanceProjection,
}


# ── Helpers ──────────────────────────────────────────────────────

def _serialise_value(val: Any) -> Any:
    """Convert a field value to JSON-serialisable form."""
    if val is None:
        return None
    if isinstance(val, ProjectionId):
        return val.value
    if isinstance(val, ProjectionType):
        return val.name
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, tuple):
        return [str(v) for v in val]
    if isinstance(val, dict):
        return {k: _serialise_value(v) for k, v in val.items()}
    return val


def _deserialise_value(val: Any, target_type: type) -> Any:
    """Convert a JSON-decoded value back to the target Python type."""
    if val is None:
        return None
    if target_type is ProjectionId:
        return ProjectionId(value=str(val))
    if target_type is ProjectionType:
        return ProjectionType[val] if isinstance(val, str) and val in ProjectionType.__members__ else val
    if hasattr(target_type, "__origin__") and target_type.__origin__ is tuple:
        # tuple[str, ...]
        return tuple(str(v) for v in val)
    if target_type is int:
        return int(val)
    if target_type is float:
        return float(val)
    if target_type is str:
        return str(val)
    if target_type is bool:
        return bool(val)
    # Handle string annotations from `from __future__ import annotations`
    # e.g. "tuple[str, ...]" → parse manually
    if isinstance(val, list):
        if isinstance(target_type, str) and "tuple" in target_type:
            return tuple(str(v) for v in val)
        if hasattr(target_type, "__origin__") and target_type.__origin__ is tuple:
            return tuple(str(v) for v in val)
    return val


# ── Encode / Decode ──────────────────────────────────────────────

def encode_projection(projection: Projection) -> dict[str, Any]:
    """Encode a Projection into a JSON-safe dict.

    The dict stores:
      - projection_id: str
      - projection_type: str (name from ProjectionType enum)
      - fields: dict of all extra dataclass fields
    """
    ptype = projection.projection_type
    ptype_name = ptype.name if isinstance(ptype, ProjectionType) else str(ptype)

    fields_dict: dict[str, Any] = {}
    if is_dataclass(projection):
        for f in dc_fields(projection):
            if f.name in ("projection_id", "projection_type"):
                continue
            val = getattr(projection, f.name)
            fields_dict[f.name] = _serialise_value(val)

    return {
        "projection_id": projection.projection_id.value,
        "projection_type": ptype_name,
        "fields": fields_dict,
    }


def decode_projection(data: dict[str, Any]) -> Projection:
    """Reconstruct a Projection from a JSON-decoded dict.

    Expects dict shape produced by encode_projection().
    Falls back to generic ProjectionData if class not in registry.
    """
    ptype_name = data.get("projection_type", "")
    ptype = None
    for pt in ProjectionType:
        if pt.name == ptype_name:
            ptype = pt
            break
    if ptype is None:
        raise ValueError(f"Unknown projection type: {ptype_name}")

    proj_cls = PROJECTION_CLASSES.get(ptype)
    if proj_cls is None:
        raise ValueError(f"No registered class for ProjectionType.{ptype_name}")

    fields_data = data.get("fields", {})

    # Reconstruct: start with projection_id and projection_type
    kwargs: dict[str, Any] = {
        "projection_id": ProjectionId(value=data["projection_id"]),
        "projection_type": ptype,
    }

    # Add remaining fields from dataclass definition
    for f in dc_fields(proj_cls):
        if f.name in ("projection_id", "projection_type"):
            continue
        if f.name in fields_data:
            kwargs[f.name] = _deserialise_value(fields_data[f.name], f.type)

    return proj_cls(**kwargs)


# ── Digest serialisation ─────────────────────────────────────────

def encode_digest(digest: ProjectionDigest) -> dict[str, Any]:
    """Encode ProjectionDigest to JSON-safe dict."""
    return {
        "revision_id": digest.revision_id,
        "revision_number": digest.revision_number,
        "graph_hash": digest.graph_hash,
        "metadata_hash": digest.metadata_hash,
    }


def decode_digest(data: dict[str, Any] | None) -> ProjectionDigest | None:
    """Decode ProjectionDigest from JSON-decoded dict."""
    if data is None:
        return None
    return ProjectionDigest(
        revision_id=data.get("revision_id", ""),
        revision_number=data.get("revision_number", -1),
        graph_hash=data.get("graph_hash", "0"),
        metadata_hash=data.get("metadata_hash", "0"),
    )


from enum import Enum  # noqa: E402 — needed for _serialise_value
