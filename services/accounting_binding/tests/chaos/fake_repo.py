"""Fake Journal Repository для chaos тестов."""
from __future__ import annotations

from contracts import JournalEntry
from domain.posting.poster import JournalRepository


class FakeJournalRepo(JournalRepository):
    def __init__(self):
        self._store: dict[str, JournalEntry] = {}
        self._by_hash: dict[str, JournalEntry] = {}

    async def try_insert(self, entry: JournalEntry) -> JournalEntry:
        existing = self._by_hash.get(entry.posting_hash)
        if existing:
            return existing
        self._store[entry.entry_id] = entry
        self._by_hash[entry.posting_hash] = entry
        return entry

    async def find_by_document(self, doc_id: str) -> list[JournalEntry]:
        return [e for e in self._store.values() if e.accounting_document_id == doc_id]
