"""Memory Service — conversational memory for Knowledge Agent.

Maintains conversational context per user session.
Supports follow-up questions, reasoning continuity.
Isolated per user — no cross-session data leaks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class MemoryMessage:
    """A single turn in conversational memory."""
    role: str          # "user" | "assistant" | "system"
    content: str
    token_count: int
    created_at: datetime | None = None
    correlation_id: str | None = None


@dataclass
class MemoryContext:
    """Context returned to Context Builder."""
    session_id: UUID
    messages: list[MemoryMessage] = field(default_factory=list)
    turn_count: int = 0
    is_expired: bool = False


@dataclass
class MemorySessionSummary:
    """Summary of a session for API responses."""
    id: UUID
    title: str | None
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    is_active: bool
    message_count: int
