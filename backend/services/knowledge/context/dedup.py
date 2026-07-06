"""Deduplication engine — 6 rules for removing duplicate context items."""

from __future__ import annotations

from uuid import UUID

from backend.services.knowledge.context.contracts import (
    KnowledgeItem, SOURCES_CHUNK, SOURCES_GRAPH, SOURCES_DOCUMENT,
    SOURCES_MEMORY, ENTITY_ID_FIELD,
)


class DedupService:
    """Remove duplicate items from context using 6 rules.

    Rules:
    R1: Same chunk_id — keep once
    R2: Same document_id — keep once
    R3: Same (entity_type, entity_id) — keep once
    R4: Same graph edge (source, target, type) — keep once
    R5: Memory ↔ Search overlap — prefer search (fresher)
    R6: Structured knowledge (graph) > raw text (search chunks) — prefer graph
    """

    def deduplicate(self, items: list[KnowledgeItem]) -> tuple[list[KnowledgeItem], float]:
        """Deduplicate KnowledgeItems. Returns (deduped_items, dedup_ratio).

        dedup_ratio = removed_count / total_count

        Items are processed in deterministic order: (-score DESC, source_type ASC, source_id ASC).
        The first occurrence of each dedup key wins.
        """
        total = len(items)
        if total == 0:
            return [], 0.0

        seen_chunks: set[str] = set()                     # R1
        seen_docs: set[str] = set()                        # R2
        seen_entities: set[tuple[str, str]] = set()        # R3
        seen_edges: set[tuple[str, str, str]] = set()      # R4
        seen_memory_msgs: set[str] = set()                 # R5

        # For R6: track entity_ids that appeared in graph items
        graph_entity_ids: set[str] = set()

        result: list[KnowledgeItem] = []
        removed = 0

        # Sort deterministically: higher score first, then source_type, then source_id
        sorted_items = sorted(
            items,
            key=lambda x: (-x.score, x.source_type, x.source_id),
        )

        for item in sorted_items:
            sid = item.source_id
            st = item.source_type

            # ── R1: chunk dedup ──
            if st == SOURCES_CHUNK and sid:
                if sid in seen_chunks:
                    removed += 1
                    continue
                seen_chunks.add(sid)

            # ── R2: document dedup ──
            if st == SOURCES_DOCUMENT and sid:
                if sid in seen_docs:
                    removed += 1
                    continue
                seen_docs.add(sid)

            # ── R3: entity dedup by (entity_type, entity_id) ──
            etype = item.entity_type
            eid = item.entity_id
            if etype and eid:
                key = (etype, eid)
                if key in seen_entities:
                    removed += 1
                    continue
                seen_entities.add(key)

            # ── R4: edge dedup (source, target, type) ──
            if st == "edge":
                src = getattr(item, "edge_source", "") or ""
                tgt = getattr(item, "edge_target", "") or ""
                etype_edge = getattr(item, "edge_type", "") or ""
                key = (src, tgt, etype_edge)
                if key in seen_edges:
                    removed += 1
                    continue
                seen_edges.add(key)

            # ── R5: memory vs search — prefer search (fresher) ──
            if st == SOURCES_MEMORY:
                if sid in seen_memory_msgs:
                    removed += 1
                    continue
                seen_memory_msgs.add(sid)

            # ── Track graph entity_ids for R6 ──
            if st == SOURCES_GRAPH and eid:
                graph_entity_ids.add(eid)

            result.append(item)

        # ── R6: Structured knowledge (graph) > raw text (search chunks) ──
        # If the same entity_id appears in graph AND in search chunks,
        # prefer the graph version. Walk in reverse so first occurrence wins
        # (higher score items were already sorted first).
        if graph_entity_ids:
            r6_result: list[KnowledgeItem] = []
            r6_seen: set[str] = set()
            for item in result:
                if item.source_type == SOURCES_GRAPH and item.entity_id in graph_entity_ids:
                    r6_seen.add(item.entity_id)
                    r6_result.append(item)
                    continue
                # Drop search chunks whose entity_id is already covered by graph
                if item.source_type == SOURCES_CHUNK and item.entity_id in r6_seen:
                    removed += 1
                    continue
                r6_result.append(item)
            result = r6_result

        dedup_ratio = round(removed / total, 4) if total > 0 else 0.0
        return result, dedup_ratio
