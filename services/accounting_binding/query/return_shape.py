"""
ReturnShape — describes the expected result shape.

Does NOT build or execute. Only describes.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Sequence

from query.property_reference import PropertyReference


class ReturnShapeType(Enum):
    """Форма результата. Не строит. Не исполняет."""
    FULL_PROJECTION = auto()
    FIELDS = auto()
    SUMMARY = auto()
    IDENTIFIERS_ONLY = auto()


@dataclass(frozen=True)
class ReturnShape:
    """Форма ожидаемого результата.

    ReturnShape ничего не строит.
    Он только описывает ожидаемый результат.
    """
    shape_type: ReturnShapeType

    # For FIELDS type: which fields to return
    fields: tuple[PropertyReference, ...] = ()

    def __post_init__(self) -> None:
        if self.shape_type == ReturnShapeType.FIELDS and not self.fields:
            raise ValueError("FIELDS shape requires at least one field")
        if self.shape_type != ReturnShapeType.FIELDS and self.fields:
            raise ValueError("Non-FIELDS shape must not have fields")
