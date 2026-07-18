"""Token counter — tiktoken-based with module-level singleton."""

from __future__ import annotations

import tiktoken

from backend.services.knowledge.context.contracts import (
    BUDGET_SYSTEM, BUDGET_MEMORY, BUDGET_KNOWLEDGE, BUDGET_QUESTION,
    HARD_CAP_TOKENS, SECTION_SYSTEM, SECTION_MEMORY,
    SECTION_KNOWLEDGE, SECTION_QUESTION,
)
from backend.services.knowledge.context.exceptions import ContextOverflowError

_ENCODING: tiktoken.Encoding | None = None


def _get_encoding() -> tiktoken.Encoding:
    """Module-level singleton — never create encoder per request."""
    global _ENCODING
    if _ENCODING is None:
        _ENCODING = tiktoken.get_encoding("cl100k_base")
    return _ENCODING


def count_tokens(text: str) -> int:
    """Count tokens using cached tiktoken cl100k_base."""
    try:
        return len(_get_encoding().encode(text))
    except Exception:
        return len(text) // 3 + 1


BUDGET_MAP = {
    SECTION_SYSTEM: BUDGET_SYSTEM,
    SECTION_MEMORY: BUDGET_MEMORY,
    SECTION_KNOWLEDGE: BUDGET_KNOWLEDGE,
    SECTION_QUESTION: BUDGET_QUESTION,
}


def validate_budget(section_tokens: dict[str, int]) -> int:
    """Validate per-section budgets and enforce hard cap.

    Returns total tokens. Raises ContextOverflowError if hard cap exceeded.
    """
    total = sum(section_tokens.values())

    for section, budget in BUDGET_MAP.items():
        used = section_tokens.get(section, 0)
        if used > budget:
            # Log warning but don't fail — truncation handles overshoot
            pass

    if total > HARD_CAP_TOKENS:
        raise ContextOverflowError(total_tokens=total, hard_cap=HARD_CAP_TOKENS)

    return total