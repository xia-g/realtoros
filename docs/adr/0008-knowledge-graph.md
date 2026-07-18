|# ADR-0008|

Date: 2026-06-07|

## Context

The system needs a unified query layer over all domain entities that supports relationship traversal, path finding, semantic search, and entity recommendation. Existing foreign keys provide implicit relationships but cannot express inferred connections, cross-entity paths, or graph analytics.

## Decision

Build a knowledge graph on PostgreSQL using an adjacency list model with two core tables:

1. **`graph_nodes`** — unified node registry over all entity tables (client, property, deal, document, etc.) with human-readable labels and pgvector embeddings (384d).
2. **`graph_edges`** — typed, weighted, time-bound edges with JSONB properties and confidence scores.

**Three edge sources:**
- **FK edges** — materialized from existing foreign key constraints (schema-driven)
- **Extraction edges** — created from document pipeline (document → entity, entity → entity)
- **AI edges** — inferred from patterns (same address, shared deals, frequent communication)

**Query patterns:** 1-hop neighborhood, n-hop path finding (recursive CTE), subgraph extraction, embedding-based semantic search, collaborative filtering recommendations.

## Reason

- **No additional infrastructure** — runs on existing PostgreSQL 17 with pgvector. No Neo4j, no separate service
- **Adjacency list** — most flexible in SQL: supports recursive CTEs, arbitrary edge types, future expansion
- **Three-tier construction** — FK edges are always correct, extraction edges are document-sourced, AI edges add latent relationships
- **Embedding search** — HNSW indexes on 384d vectors enable semantic graph queries
- **Incremental maintenance** — database triggers auto-create nodes on entity insert; scheduled jobs handle expiry and re-indexing

## Status

Accepted
