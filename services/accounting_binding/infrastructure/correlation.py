"""
Correlation Context для аудита и диагностики.

Разделение:
- trace_id: внешний (HTTP запрос, OCR job)
- pipeline_run_id: один прогон pipeline.run()
- replay_id: если это replay
- causation_id: какое событие вызвало это
- correlation_id: связь между разными сервисами

Все поля опциональны — обязателен только trace_id.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class CorrelationContext:
    """Контекст корреляции для одного прогона pipeline."""
    trace_id: str = ""
    pipeline_run_id: str = ""
    replay_id: str = ""
    causation_id: str = ""
    correlation_id: str = ""

    @classmethod
    def new(cls, trace_id: str = "") -> "CorrelationContext":
        """Создать новый контекст с автоматическими ID."""
        run_id = str(uuid4())
        return cls(
            trace_id=trace_id or run_id,
            pipeline_run_id=run_id,
            correlation_id=run_id,
        )

    @classmethod
    def from_replay(cls, trace_id: str, replay_id: str, original_run_id: str) -> "CorrelationContext":
        """Создать контекст для replay."""
        return cls(
            trace_id=trace_id,
            pipeline_run_id=str(uuid4()),
            replay_id=replay_id,
            causation_id=original_run_id,
            correlation_id=original_run_id,
        )

    def to_dict(self) -> dict[str, str]:
        """Для сериализации в JSON."""
        return {
            k: v for k, v in {
                "trace_id": self.trace_id,
                "pipeline_run_id": self.pipeline_run_id,
                "replay_id": self.replay_id,
                "causation_id": self.causation_id,
                "correlation_id": self.correlation_id,
            }.items() if v
        }
