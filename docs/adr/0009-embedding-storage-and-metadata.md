|# ADR-0009|

Date: 2026-06-07|

## Context

Architecture audit V1 identified two critical schema issues:

1. **Embedding storage duplication:** `entity_resolution.md` stores embeddings on entity tables (`clients.embedding`, `properties.embedding`) plus a separate `entity_embeddings` table. `knowledge_graph.md` stores embeddings on `graph_nodes.embedding`. Three possible locations for the same data with no synchronization strategy.

2. **Undefined `documents_metadata`:** `entity_extraction.md` references a `documents_metadata` table for extracted dates, prices, and organizations that does not exist anywhere in the schema.

## Decision

### 1. Embedding Storage — Entity-Attached Model

Embeddings are stored ON the entity tables that own them:

- `clients.embedding` — for client entity resolution
- `clients.name_embedding` — for client name-specific similarity
- `properties.embedding` — for property entity resolution

The separate `entity_embeddings` table is **removed**. The `graph_nodes.embedding` column is **removed**.

**Graph nodes will JOIN to entity tables for embeddings** — no redundant storage. The graph query layer retrieves embeddings via:

```sql
SELECT gn.id, gn.label, c.embedding
FROM graph_nodes gn
JOIN clients c ON c.id = gn.entity_id
WHERE gn.entity_table = 'clients';
```

**Embedding computation:** Performed in Python by `EmbeddingMatcher` using `sentence-transformers`. The `pgml` extension is **not required** — all embedding logic stays in the application layer.

### 2. `documents_metadata` — Stored in `extracted_entities.extraction_data` JSONB

Extracted dates, prices, and organizations are stored in the `extracted_entities.extraction_data` JSONB field. No separate table is created.

```json
// extraction_data JSONB structure for dates/prices/organizations
{
  "clients": [...],
  "properties": [...],
  "deals": [...],
  "dates": [{"value": "2026-01-15", "context": "contract_date", "confidence": 0.95}],
  "prices": [{"amount": 5000000, "currency": "RUB", "context": "sale_price", "confidence": 0.99}],
  "organizations": [{"name": "Росреестр", "role": "rosreestr", "confidence": 0.90}],
  "addresses": [{"full": "г. Москва, ул. Ленина, д. 5", "context": "property", "confidence": 0.95}]
}
```

When extraction is `applied` (status = 'applied'), relevant data is propagated to domain tables:
- Dates → `deals.start_date`, `deals.closing_date`, `clients.birth_date`, `documents.expiry_date`
- Prices → `deals.price`, `deals.deposit_amount`
- Organizations → `clients` (as `type='partner'`)

## Reason

- **Entity-attached embeddings:** Single source of truth. No sync needed. Graph queries are slightly more expensive (JOIN) but this is negligible for 100K node scale.
- **No `pgml` required:** Python embedding computation is simpler to maintain, test, and debug. Removes an extension dependency.
- **JSONB for metadata:** Avoids table proliferation. 9 new tables already proposed; adding more would increase migration complexity. Extracted metadata is transient — it becomes domain data when applied.
- **Application-layer parsing:** Dates and prices are extracted -> validated -> promoted to domain fields. JSONB preserves the original extraction result for audit.

## Status

Accepted
