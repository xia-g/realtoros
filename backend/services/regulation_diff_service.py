"""Regulation Diff Service — сравнение версий нормативных актов."""

from __future__ import annotations

import difflib
import re

from structlog import get_logger

logger = get_logger(__name__)


class RegulationDiffService:
    """Сравнение версий нормативных актов."""

    SEVERITY_KEYWORDS = {
        "critical": ["обязан", "запрещается", "не допускается", "утратил силу"],
        "high": ["изменён", "дополнен", "новая редакция"],
        "medium": ["уточнён", "разъяснён"],
        "low": ["рекомендуется", "может"],
    }

    async def diff_regulation(self, old_content: str, new_content: str) -> dict:
        """Сравнить две версии документа."""
        diff = list(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            lineterm="",
        ))

        added = [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")]
        removed = [l[1:] for l in diff if l.startswith("-") and not l.startswith("---")]

        return {
            "has_changes": len(added) > 0 or len(removed) > 0,
            "added_lines": len(added),
            "removed_lines": len(removed),
            "added_sections": added[:10],
            "removed_sections": removed[:10],
        }

    async def summarize_changes(self, diff_result: dict, old_version: str, new_version: str) -> str:
        """Суммировать изменения в human-readable формате."""
        if not diff_result["has_changes"]:
            return "Изменений не обнаружено"
        parts = []
        if diff_result["added_lines"]:
            parts.append(f"Добавлено {diff_result['added_lines']} фрагментов")
        if diff_result["removed_lines"]:
            parts.append(f"Удалено {diff_result['removed_lines']} фрагментов")
        return f"Версия {old_version} → {new_version}: {'; '.join(parts)}"

    async def classify_impact(self, content: str) -> str:
        """Классифицировать уровень влияния изменений."""
        for level, keywords in self.SEVERITY_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in content.lower():
                    return level
        return "low"
