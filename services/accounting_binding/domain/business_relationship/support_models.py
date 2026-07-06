"""
Alias, MergeCandidate, ConfidenceHistory — support models for Identity Resolution.
All in-memory. NO DB writes.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AliasType(str, Enum):
    NAME_VARIANT = "name_variant"       # другая форма названия
    ABBREVIATION = "abbreviation"       # сокращение
    TRANSLITERATION = "transliteration" # транслитерация
    TYPO = "typo"                        # опечатка
    HISTORICAL = "historical"            # историческое название


@dataclass
class Alias:
    """Альтернативное представление сущности."""
    original_value: str
    normalized_value: str
    alias_type: AliasType = AliasType.NAME_VARIANT
    confidence: float = 0.8
    source_document: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


class MergeDecision(str, Enum):
    AUTO_MERGE = "auto_merge"        # ≥99 — автоматически объединить
    REVIEW_MERGE = "review_merge"    # 95-99 — на проверку
    NO_MERGE = "no_merge"            # <95 — разные сущности


@dataclass
class MergeCandidate:
    """Пара сущностей-кандидатов на объединение."""
    left_entity_id: str
    right_entity_id: str
    similarity_score: float = 0.0
    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)

    @property
    def decision(self) -> MergeDecision:
        if self.similarity_score >= 99:
            return MergeDecision.AUTO_MERGE
        elif self.similarity_score >= 95:
            return MergeDecision.REVIEW_MERGE
        return MergeDecision.NO_MERGE


@dataclass
class ConfidencePoint:
    """Одно подтверждение сущности."""
    source_document_id: str
    source_agreement_id: str = ""
    confidence_delta: float = 0.1     # на сколько увеличилась уверенность
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConfidenceHistory:
    """История подтверждений сущности. Append-only."""
    entity_id: str
    initial_confidence: float = 0.0
    points: list[ConfidencePoint] = field(default_factory=list)

    def add(self, doc_id: str, agreement_id: str = "", delta: float = 0.1):
        self.points.append(ConfidencePoint(
            source_document_id=doc_id,
            source_agreement_id=agreement_id,
            confidence_delta=delta,
        ))

    @property
    def current_confidence(self) -> float:
        return min(1.0, self.initial_confidence + sum(p.confidence_delta for p in self.points))

    @property
    def confirmation_count(self) -> int:
        return len(self.points)
