"""Pipeline domain model — state machine, models, constants."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ─── Lifecycle ───────────────────────────────────────────────────


class PipelineStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    OCR_COMPLETED = "OCR_COMPLETED"
    CLASSIFIED = "CLASSIFIED"
    EXTRACTED = "EXTRACTED"
    KNOWLEDGE_BOUND = "KNOWLEDGE_BOUND"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


VALID_PIPELINE_TRANSITIONS: dict[str, list[str]] = {
    "PENDING": ["RUNNING"],
    "RUNNING": ["OCR_COMPLETED", "FAILED"],
    "OCR_COMPLETED": ["CLASSIFIED", "FAILED", "NEEDS_REVIEW"],
    "CLASSIFIED": ["EXTRACTED", "FAILED"],
    "EXTRACTED": ["KNOWLEDGE_BOUND", "FAILED"],
    "KNOWLEDGE_BOUND": ["COMPLETED", "FAILED"],
    "COMPLETED": [],
    "FAILED": ["PENDING"],  # retry
    "NEEDS_REVIEW": ["RUNNING", "COMPLETED"],
}

# Step execution order
PIPELINE_STEP_ORDER = ["ocr", "quality", "classification", "extraction", "knowledge"]


# ─── Models ──────────────────────────────────────────────────────


@dataclass
class PipelineStep:
    step_id: str = ""
    pipeline_id: str = ""
    step_type: str = ""
    status: str = "PENDING"
    order_index: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class PipelineRun:
    pipeline_id: str = ""
    document_id: str = ""
    status: str = "PENDING"
    created_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class OCRResult:
    raw_text: str = ""
    confidence: float = 0.0
    language: str = ""
    page_count: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class QualityResult:
    ocr_confidence: float = 0.0
    overall_score: float = 0.0
    needs_review: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class ClassificationResult:
    document_type: str = ""
    confidence: float = 0.0
    alternatives: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class ExtractionResult:
    fields: dict = field(default_factory=dict)
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)


@dataclass
class KnowledgeBindingResult:
    knowledge_revision_id: str = ""
    confidence: float = 0.0


# ─── State machine ────────────────────────────────────────────────


def validate_pipeline_transition(current: str, target: str) -> str | None:
    """Check if pipeline state transition is allowed."""
    if current == target:
        return None
    allowed = VALID_PIPELINE_TRANSITIONS.get(current, [])
    if target not in allowed:
        return f"Pipeline transition {current} → {target} not allowed"
    return None


def transition_pipeline(pipeline: PipelineRun, target: str) -> str | None:
    """Transition pipeline to target state. Returns error or None."""
    err = validate_pipeline_transition(pipeline.status, target)
    if err:
        return err
    pipeline.status = target
    return None


# ─── Step helpers ────────────────────────────────────────────────


STEP_LABELS: dict[str, str] = {
    "ocr": "OCR",
    "quality": "Quality Assessment",
    "classification": "Classification",
    "extraction": "Entity Extraction",
    "knowledge": "Knowledge Binding",
}

STEP_TO_PIPELINE_STATUS: dict[str, str] = {
    "ocr": "OCR_COMPLETED",
    "classification": "CLASSIFIED",
    "extraction": "EXTRACTED",
    "knowledge": "KNOWLEDGE_BOUND",
}
