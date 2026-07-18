|# ADR-0007|

Date: 2026-06-07|

## Context

After entity extraction, the system must determine whether extracted entities (Client, Property, Deal, Organization) already exist in the database to prevent duplicates and enrich existing records. Exact matching is insufficient due to OCR errors, name variants, and address normalization.

## Decision

Adopt a 4-stage cascading entity resolution pipeline:

1. **Stage 1: Exact match** — phone, passport, cadastral number, INN via database unique constraints. Covers ~40% of entities.
2. **Stage 2: Fuzzy string match** — pg_trgm similarity + Levenshtein + Russian name normalization (ё→е, gender variants, initials, Soundex). Covers ~30%.
3. **Stage 3: Embedding similarity** — pgvector cosine distance with multilingual-e5-small model (384d). Covers ~10%.
4. **Stage 4: Review & Merge** — weighted confidence scoring from all signals. Auto-merge ≥ 0.85, warn ≥ 0.75, human review ≥ 0.50, new entity < 0.50.

**Storage:** New `entity_resolutions` table stores match signals, merge log, and decision. New `resolution_reviews` table queues human review tasks with Telegram inline keyboard notifications.

**Merge strategy:** Enrich-only for clients/properties (fill missing fields, never overwrite). No auto-merge for deals (too sensitive).

## Reason

- **Multi-signal confidence:** Combining phone (1.0) + fuzzy name (0.85) yields 0.97 combined — higher than either alone
- **Conflict detection:** Conflicting signals (phone matches A, name matches B) trigger human review, preventing false merges
- **Embedding robustness:** Semantic similarity catches OCR-damaged names and address variants that character-based methods miss
- **Human-in-the-loop:** < 20% review rate, Telegram inline keyboard for quick resolution
- **pgvector integration:** Uses existing PostgreSQL infrastructure without additional services

## Status

Accepted
