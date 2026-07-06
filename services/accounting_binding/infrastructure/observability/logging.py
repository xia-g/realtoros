"""
Observability — Structured Logging.

Никаких свободных print/log строк.
Формат: JSON, обязательные поля.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class StructuredLogFormatter(logging.Formatter):
    """JSON-форматер для structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Correlation context (если есть)
        if hasattr(record, "trace_id"):
            log_entry["trace_id"] = record.trace_id
        if hasattr(record, "pipeline_run_id"):
            log_entry["pipeline_run_id"] = record.pipeline_run_id
        if hasattr(record, "document_id"):
            log_entry["document_id"] = record.document_id
        if hasattr(record, "step"):
            log_entry["step"] = record.step
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        # Extra
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(level: str = "INFO", json_output: bool = True) -> None:
    """Настроить structured logging."""
    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(StructuredLogFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)


def log_step(
    logger: logging.Logger,
    step: str,
    status: str,
    document_id: str = "",
    trace_id: str = "",
    duration_ms: float = 0,
    **extra,
) -> None:
    """Структурированный лог шага pipeline."""
    extra_record = logging.LogRecord(
        name=logger.name,
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=f"Step {step}: {status}",
        args=(),
        exc_info=None,
    )
    extra_record.step = step
    extra_record.status = status
    extra_record.document_id = document_id
    extra_record.trace_id = trace_id
    extra_record.duration_ms = duration_ms
    for k, v in extra.items():
        setattr(extra_record, k, v)
    logger.handle(extra_record)
