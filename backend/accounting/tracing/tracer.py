"""Simple distributed tracing — trace_id through the pipeline."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def get_trace_id() -> str:
    return trace_id_var.get()


def set_trace_id(trace_id: str | None = None) -> str:
    tid = trace_id or str(uuid.uuid4())
    trace_id_var.set(tid)
    return tid


def generate_trace_id() -> str:
    return str(uuid.uuid4())
