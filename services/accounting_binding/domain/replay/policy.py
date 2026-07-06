"""
Domain — Replay Policy.

Определяет, какие этапы пересчитывать при replay.
Без политики — расхождения между обычным прогоном и replay.
"""
from __future__ import annotations

from enum import Enum

from contracts import EnrichedDocument, AccountingDocument


class ReplayStrategy(str, Enum):
    """Стратегия replay для каждого этапа."""
    REUSE = "reuse"                # использовать существующий результат
    RECOMPUTE = "recompute"        # пересчитать с нуля
    RECOMPUTE_IF_STALE = "recompute_if_stale"  # пересчитать, если хеш не совпадает


class ReplayPolicy:
    """Политика replay — какие этапы пересчитывать.

    По умолчанию:
    - enrichment: reuse (OCR не перезапускаем)
    - validation: recompute (быстро, всегда свежий)
    - mapping: recompute_if_stale (только если enriched изменился)
    - posting: reject duplicate (UNIQUE hash)
    - reporting: recompute (disposable)
    """

    ENRICHMENT: ReplayStrategy = ReplayStrategy.REUSE
    VALIDATION: ReplayStrategy = ReplayStrategy.RECOMPUTE
    MAPPING: ReplayStrategy = ReplayStrategy.RECOMPUTE_IF_STALE
    POSTING: ReplayStrategy = ReplayStrategy.RECOMPUTE
    REPORTING: ReplayStrategy = ReplayStrategy.RECOMPUTE

    def should_recompute_enrichment(self, original: EnrichedDocument | None) -> bool:
        """Пересчитать enrichment?"""
        if self.ENRICHMENT == ReplayStrategy.RECOMPUTE:
            return True
        return original is None

    def should_recompute_mapping(
        self, original: AccountingDocument | None,
        current_enriched: EnrichedDocument,
    ) -> bool:
        """Пересчитать mapping?"""
        if self.MAPPING == ReplayStrategy.RECOMPUTE:
            return True
        if self.MAPPING == ReplayStrategy.RECOMPUTE_IF_STALE and original:
            return original.mapping_hash != current_enriched.dedup_hash
        return False

    def should_recompute_posting(
        self, original: AccountingDocument | None,
        current_accounting: AccountingDocument,
    ) -> bool:
        """Пересчитать posting?"""
        # Posting идемпотентен: UNIQUE hash → DUPLICATE
        return True
