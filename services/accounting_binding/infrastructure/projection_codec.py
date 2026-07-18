"""
ProjectionCodec — serialization/lookup helpers for Projection types.

Infrastructure uses Codecs to translate between universal storage
operations and typed Projection data.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Optional

from projection.projection import Projection, ProjectionId, ProjectionType


@dataclass(frozen=True)
class ProjectionData:
    """Raw serializable data extracted from a Projection."""
    projection_id: str
    projection_type: str
    fields: dict[str, Any]


class ProjectionCodec:
    """Codec for serializing/deserializing Projection instances.

    Stores can use this for generic put/get without knowing
    the concrete Projection type at compile time.
    """

    @staticmethod
    def encode(projection: Projection) -> ProjectionData:
        """Encode a Projection into serializable data."""
        field_values: dict[str, Any] = {}
        for f in fields(projection):
            value = getattr(projection, f.name)
            if f.name in ('projection_id', 'projection_type'):
                continue
            # Convert nested objects to string representation
            if hasattr(value, 'value'):
                field_values[f.name] = value.value
            elif isinstance(value, tuple):
                field_values[f.name] = [str(v) for v in value]
            else:
                field_values[f.name] = value

        return ProjectionData(
            projection_id=projection.projection_id.value,
            projection_type=projection.projection_type.name,
            fields=field_values,
        )

    @staticmethod
    def decode(
        data: ProjectionData,
        projection_class: type,
    ) -> Projection:
        """Decode ProjectionData back into a concrete Projection class.

        Args:
            data: serialized projection data
            projection_class: the concrete frozen dataclass to reconstruct

        Returns:
            reconstructed Projection instance
        """
        constructor_args: dict[str, Any] = {
            'projection_id': ProjectionId(value=data.projection_id),
            'projection_type': ProjectionType[data.projection_type],
        }
        for f in fields(projection_class):
            if f.name in constructor_args:
                continue
            if f.name in data.fields:
                constructor_args[f.name] = data.fields[f.name]

        return projection_class(**constructor_args)
