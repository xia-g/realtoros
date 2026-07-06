# Knowledge Graph Construction Layer

## Overview

Builds and maintains a unified property graph over all domain entities using PostgreSQL only. Transforms implicit foreign-key relationships and document-derived connections into explicit, typed, queryable graph edges.

```
Entity Tables (clients, properties, deals, ...)
    │
    ▼
┌─────────────────────────────────────────────┐
│  Graph Construction                          │
│                                             │
│  1. FK → Graph Edges (schema-driven)         │
│  2. Document → Graph Edges (extraction)      │
│  3. AI → Graph Edges (inferred relations)    │
│  4. Graph Maintenance (dedup, expiry)        │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  Query Layer                                 │
│                                             │
│  ├─ Nearest neighbor (1-hop)                │
│  ├─ Path finding (recursive CTE)            │
│  ├─ Subgraph extraction                     │
│  ├─ Aggregation (centrality, clustering)    │
│  └─ AI-enabled queries (embedding search)   │
└─────────────────────────────────────────────┘
```

## Storage Model

### Design Decision: Adjacency List with Typed Edges

PostgreSQL does not natively support Gremlin or Cypher. The graph is modelled as an **adjacency list** with a single `relationships` table. This is the most flexible, queryable, and extensible approach in relational SQL.

```sql
-- Comparison of approaches
--
│ Approach              │ Queryability │ Performance │ Flexibility │
│──────────────────────────┼──────────────┼──────────────┼──────────────│
│ FK-only (existing)     │ Poor (fixed) │ Excellent    │ None        │
│ Adjacency list (this) │ Excellent    │ Good (with indexes) │ High │
│ JSONB inside entities │ Poor (no traversal) │ Good │ Medium      │
│ Materialized paths    │ Medium       │ Poor on update │ Low        │
```

### Core Tables

```sql
-- ============================================================
-- Knowledge Graph — Core Tables
-- PostgreSQL 17, pgvector extension required
-- ============================================================

-- 1. Node types registry (metadata, not instances)
CREATE TYPE node_type AS ENUM (
    'client',
    'client_contact',
    'property',
    'deal',
    'deal_participant',
    'document',
    'document_classification',
    'communication',
    'task',
    'user',
    'role',
    'organization',       -- extracted from documents
    'address',            -- extracted from documents
    'price_record',       -- monetary events
    'date_event',         -- timeline nodes
    'phone_number',       -- contact point nodes
    'email_address'       -- contact point nodes
);

CREATE TYPE edge_type AS ENUM (
    -- Ownership & identity
    'owns',                -- client → property
    'owned_by',            -- property → client (inverse)

    -- Deal relationships
    'participates_in',     -- client → deal (via deal_participant)
    'has_participant',     -- deal → client (via deal_participant)
    'subject_of',          -- property → deal
    'involves_property',   -- deal → property

    -- Document relationships
    'refers_to_client',    -- document → client
    'refers_to_property',  -- document → property
    'refers_to_deal',      -- document → deal
    'uploaded_by',         -- document → user
    'classified_as',       -- document → document_classification

    -- Communication
    'communicated_with',   -- communication → client
    'about_deal',          -- communication → deal
    'created_by_user',     -- communication → user
    'assigned_to_user',    -- communication → user

    -- Task
    'task_for_client',     -- task → client
    'task_for_deal',       -- task → deal
    'task_for_property',   -- task → property
    'assigned_to',         -- task → user
    'created_task',        -- user → task

    -- Contact
    'has_contact',         -- client → client_contact
    'contact_of',          -- client_contact → client

    -- Extracted relationships (from document pipeline)
    'extracted_from',      -- any entity → document
    'mentioned_in',        -- any entity → document
    'same_as',             -- entity → entity (dedup / alias)
    'related_to',          -- entity → entity (generic)

    -- Temporal
    'precedes',            -- date_event → date_event
    'follows',             -- date_event → date_event (inverse)

    -- Address
    'registered_at',       -- client → address
    'located_at',          -- property → address

    -- Organizational
    'employs',             -- organization → client
    'employed_by',         -- client → organization
    'represents'           -- client → client (power of attorney)
);

-- 2. Nodes — unified view of all entities
CREATE TABLE graph_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_type node_type NOT NULL,
    entity_id UUID NOT NULL,           -- FK to the actual entity table
    entity_table VARCHAR(50) NOT NULL, -- 'clients', 'properties', etc.
    label VARCHAR(255) NOT NULL,       -- human-readable label
    properties JSONB NOT NULL DEFAULT '{}',
    embedding vector(384),             -- optional: for semantic graph search
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Each entity maps to exactly one node
    UNIQUE (entity_table, entity_id)
);

-- 3. Edges — typed relationships between nodes
CREATE TABLE graph_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_node_id UUID NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    edge_type edge_type NOT NULL,

    -- Edge metadata
    weight FLOAT DEFAULT 1.0,         -- relationship strength
    properties JSONB NOT NULL DEFAULT '{}',
    -- Examples:
    -- { "role": "buyer", "confidence": 0.95 }  for participates_in
    -- { "document_id": "uuid", "date": "2026-01-15" }  for extracted_from
    -- { "amount": 5000000, "currency": "RUB" }  for subject_of

    source VARCHAR(50) NOT NULL DEFAULT 'fk',  -- 'fk', 'extraction', 'ai', 'manual'
    confidence FLOAT DEFAULT 1.0,
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Prevent duplicate edges
    UNIQUE (source_node_id, target_node_id, edge_type)
);

-- Indexes
CREATE INDEX idx_graph_nodes_type ON graph_nodes(node_type);
CREATE INDEX idx_graph_nodes_entity ON graph_nodes(entity_table, entity_id);
CREATE INDEX idx_graph_nodes_label ON graph_nodes USING GIN (label gin_trgm_ops);

CREATE INDEX idx_graph_edges_source ON graph_edges(source_node_id);
CREATE INDEX idx_graph_edges_target ON graph_edges(target_node_id);
CREATE INDEX idx_graph_edges_type ON graph_edges(edge_type);
CREATE INDEX idx_graph_edges_source_type ON graph_edges(source_node_id, edge_type);
CREATE INDEX idx_graph_edges_target_type ON graph_edges(target_node_id, edge_type);

-- HNSW index for embedding-based graph search (pgvector)
CREATE INDEX idx_graph_nodes_embedding
    ON graph_nodes USING hnsw (embedding vector_cosine_ops);
```

## Graph Construction

### Source 1: Foreign Key Relationships (Schema-Driven)

Existing FK relationships in the domain model are materialized as graph edges.

```python
class FKGraphBuilder:
    """Builds graph edges from existing database foreign keys.

    Runs on:
    - Initial graph bootstrap (one-time)
    - Incremental after each entity insert
    """

    FK_MAPPINGS = [
        # (entity_table, fk_column, target_table, edge_type, inverse_type)

        # Client → Property
        ("properties", "owner_id", "clients",
         "owned_by", "owns"),

        # Property → Deal
        ("deals", "property_id", "properties",
         "involves_property", "subject_of"),

        # Deal → User (creator)
        ("deals", "created_by", "users",
         "created_by_user", "created_deal"),

        # Deal → DealParticipant → Client
        ("deal_participants", "deal_id", "deals",
         "belongs_to", "has_participant"),
        ("deal_participants", "client_id", "clients",
         "participates_in", "has_client"),

        # Client → ClientContact
        ("client_contacts", "client_id", "clients",
         "contact_of", "has_contact"),

        # Document → Client/Property/Deal
        ("documents", "client_id", "clients",
         "refers_to_client", "has_document"),
        ("documents", "property_id", "properties",
         "refers_to_property", "has_document"),
        ("documents", "deal_id", "deals",
         "refers_to_deal", "has_document"),
        ("documents", "uploaded_by", "users",
         "uploaded_by", "uploaded"),

        # Communication → Client/Deal/User
        ("communications", "client_id", "clients",
         "communicated_with", "has_communication"),
        ("communications", "deal_id", "deals",
         "about_deal", "has_communication"),
        ("communications", "created_by", "users",
         "created_by_user", "created_communication"),
        ("communications", "assigned_to", "users",
         "assigned_to_user", "assigned_communication"),

        # Task → Client/Deal/Property/User
        ("tasks", "client_id", "clients",
         "task_for_client", "has_task"),
        ("tasks", "deal_id", "deals",
         "task_for_deal", "has_task"),
        ("tasks", "property_id", "properties",
         "task_for_property", "has_task"),
        ("tasks", "assigned_to", "users",
         "assigned_to", "has_task_assigned"),
        ("tasks", "created_by", "users",
         "created_task", "task_creator"),

        # User → Role
        ("users", "role_id", "roles",
         "has_role", "has_user"),
    ]

    async def build_all(self, session):
        """Bootstrap the entire graph from existing data."""
        for node_type, table in self.NODE_TYPES:
            await self._populate_nodes(session, node_type, table)
        for mapping in self.FK_MAPPINGS:
            await self._build_fk_edges(session, mapping)
        await session.commit()

    async def _build_fk_edges(self, session, mapping):
        """Build edges from FK relationships in bulk."""
        source_table, fk_col, target_table, edge, inverse = mapping

        await session.execute(text(f"""
            INSERT INTO graph_edges (
                source_node_id, target_node_id, edge_type,
                source, confidence, created_at
            )
            SELECT
                src.id AS source_node_id,
                tgt.id AS target_node_id,
                :edge_type AS edge_type,
                'fk' AS source,
                1.0 AS confidence,
                NOW() AS created_at
            FROM {source_table} AS s
            JOIN graph_nodes AS src
                ON src.entity_table = '{source_table}'
                AND src.entity_id = s.id
            JOIN graph_nodes AS tgt
                ON tgt.entity_table = '{target_table}'
                AND tgt.entity_id = s.{fk_col}
            WHERE s.{fk_col} IS NOT NULL
            ON CONFLICT (source_node_id, target_node_id, edge_type)
            DO NOTHING
        """), {"edge_type": edge})
```

### Source 2: Document Extraction Results

When the document pipeline extracts entities, those connections become graph edges.

```python
class ExtractionGraphBuilder:
    """Builds graph edges from document extraction results.

    Creates edges between:
    - document → extracted entities (extracted_from)
    - entities discovered as related by the document
    """

    async def build_from_extraction(
        self,
        session,
        document_id: UUID,
        extraction: ExtractionResult,
        resolution: ResolutionResult,
    ):
        """Build edges for all entities extracted from one document."""

        doc_node = await self._get_or_create_node(
            session, "document", document_id,
        )

        # 1. Document → each extracted entity
        for entity_type in ("clients", "properties", "deals", "organizations"):
            for entity in extraction.entities.get(entity_type, []):
                target_id = resolution.resolved_ids.get(entity.id)
                if target_id:
                    target_node = await self._get_or_create_node(
                        session, entity_type, target_id,
                    )
                    await self._create_edge(
                        session,
                        source=doc_node.id,
                        target=target_node.id,
                        edge_type="extracted_from"
                        if entity_type == "document"
                        else "mentioned_in",
                        properties={
                            "confidence": entity.confidence,
                            "role": entity.get("role"),
                        },
                        source="extraction",
                    )

        # 2. Cross-entity edges from document context
        # e.g., if a sale contract mentions buyer and seller,
        # create a "contracts_with" edge between them
        clients = extraction.entities.get("clients", [])
        if len(clients) >= 2:
            for i in range(len(clients)):
                for j in range(i + 1, len(clients)):
                    id_i = resolution.resolved_ids.get(clients[i].id)
                    id_j = resolution.resolved_ids.get(clients[j].id)
                    if id_i and id_j:
                        node_i = await self._get_or_create_node(
                            session, "client", id_i,
                        )
                        node_j = await self._get_or_create_node(
                            session, "client", id_j,
                        )
                        await self._create_edge(
                            session,
                            source=node_i.id,
                            target=node_j.id,
                            edge_type="related_to",
                            properties={
                                "context": extraction.document_type,
                                "document_id": str(document_id),
                                "roles": [
                                    clients[i].role,
                                    clients[j].role,
                                ],
                            },
                            source="extraction",
                            confidence=min(
                                clients[i].confidence,
                                clients[j].confidence,
                            ),
                        )

        # 3. Entity → extracted addresses, prices, dates
        for entity_type, entities in [
            ("address", extraction.addresses),
            ("price_record", extraction.prices),
            ("date_event", extraction.dates),
        ]:
            for item in entities:
                item_node = await self._get_or_create_node(
                    session, entity_type, item.id,
                )
                # Link to the parent entity
                parent_id = resolution.resolved_ids.get(
                    item.parent_entity_id
                )
                if parent_id:
                    parent_node = await self._get_or_create_node(
                        session, item.parent_entity_type, parent_id,
                    )
                    await self._create_edge(
                        session,
                        source=parent_node.id,
                        target=item_node.id,
                        edge_type="has_detail",
                        properties={"context": entity_type},
                        source="extraction",
                        confidence=item.confidence,
                    )
```

### Source 3: AI-Inferred Relationships

Beyond explicit FK and extraction edges, the AI can infer latent relationships.

```python
class AIEdgeBuilder:
    """Builds inferred edges using AI analysis.

    Examples:
    - Two clients with same address → "cohabits" or "family_of"
    - Client + organization on same document → "employed_by"
    - Property with multiple deals → "price_history"
    - Repeated communication patterns → "frequent_contact"
    """

    INFERENCE_RULES = {
        "address_overlap": {
            "query": """
                SELECT c1.id AS client1_id,
                       c2.id AS client2_id
                FROM clients c1
                JOIN clients c2 ON c1.registration_address = c2.registration_address
                WHERE c1.id < c2.id
                  AND c1.registration_address IS NOT NULL
            """,
            "edge_type": "related_to",
            "properties": {"reason": "same_address"},
            "weight": 0.6,
        },
        "frequent_communication": {
            "query": """
                SELECT cm.client_id,
                       cm.created_by AS user_id,
                       COUNT(*) AS msg_count
                FROM communications cm
                GROUP BY cm.client_id, cm.created_by
                HAVING COUNT(*) >= 5
            """,
            "edge_type": "frequent_contact",
            "properties": {"count_column": "msg_count"},
            "weight": 0.7,
        },
        "deal_participant_overlap": {
            "query": """
                SELECT dp1.client_id AS client_a,
                       dp2.client_id AS client_b,
                       COUNT(*) AS shared_deals
                FROM deal_participants dp1
                JOIN deal_participants dp2
                    ON dp1.deal_id = dp2.deal_id
                    AND dp1.client_id < dp2.client_id
                GROUP BY dp1.client_id, dp2.client_id
                HAVING COUNT(*) >= 2
            """,
            "edge_type": "related_to",
            "properties": {"reason": "shared_deals"},
            "weight": 0.8,
        },
        "organization_client_link": {
            "query": """
                SELECT d.client_id, o.id AS org_id
                FROM documents d
                JOIN organizations o
                    ON d.document_type = 'power_of_attorney'
                    AND ... -- org name appears in document text
            """,
            "edge_type": "represents",
            "weight": 0.5,
        },
    }

    async def run_inferences(self, session):
        """Run all inference rules and create edges."""
        for rule_name, rule in self.INFERENCE_RULES.items():
            rows = await session.execute(text(rule["query"]))
            for row in rows:
                source_node = await self._get_node(
                    session, row[0], "client"
                )
                target_node = await self._get_node(
                    session, row[1], "client"
                )
                if source_node and target_node:
                    props = dict(rule["properties"])
                    for key, col in props.items():
                        if col == "count_column":
                            props[key] = row[-1]  # last column = count
                    await self._create_edge(
                        session,
                        source=source_node.id,
                        target=target_node.id,
                        edge_type=rule["edge_type"],
                        properties=props,
                        weight=rule["weight"],
                        source="ai",
                    )
```

## Query Patterns

### Pattern 1: Entity Neighborhood (1-hop)

```sql
-- Find everything connected to a specific client
SELECT
    e.edge_type,
    n.node_type AS connected_type,
    n.label AS connected_label,
    e.properties,
    e.weight
FROM graph_nodes n
JOIN graph_edges e ON e.target_node_id = n.id
WHERE e.source_node_id = (
    SELECT id FROM graph_nodes
    WHERE entity_table = 'clients' AND entity_id = :client_id
)
ORDER BY e.weight DESC;
```

```python
async def get_entity_neighborhood(
    session,
    entity_type: str,
    entity_id: UUID,
    depth: int = 1,
    edge_filter: list[str] | None = None,
) -> GraphResponse:
    """Get all entities connected to this one within N hops."""

    query = """
        WITH RECURSIVE neighborhood AS (
            -- Anchor: start node
            SELECT id, node_type, label, 0 AS depth
            FROM graph_nodes
            WHERE entity_table = :entity_table
              AND entity_id = :entity_id

            UNION

            -- Recursive: follow edges
            SELECT n.id, n.node_type, n.label, nh.depth + 1
            FROM neighborhood nh
            JOIN graph_edges e
                ON e.source_node_id = nh.id
            JOIN graph_nodes n
                ON n.id = e.target_node_id
            WHERE nh.depth < :max_depth
              AND (e.edge_type = ANY(:edge_filter) OR :edge_filter IS NULL)
        )
        SELECT DISTINCT id, node_type, label, depth
        FROM neighborhood
        ORDER BY depth, node_type
    """
    rows = await session.execute(text(query), {
        "entity_table": entity_type,
        "entity_id": entity_id,
        "max_depth": depth,
        "edge_filter": edge_filter,
    })
    return GraphResponse(nodes=rows.fetchall())
```

### Pattern 2: Path Finding

```sql
-- Find shortest path between two entities (e.g., client → property)
WITH RECURSIVE path AS (
    -- Anchor: start node
    SELECT
        n.id,
        n.label,
        0 AS depth,
        ARRAY[n.id] AS path_ids,
        ARRAY[n.label] AS path_labels
    FROM graph_nodes n
    WHERE n.entity_table = 'clients'
      AND n.entity_id = :start_id

    UNION

    -- Recursive: follow any edge
    SELECT
        n.id,
        n.label,
        p.depth + 1,
        p.path_ids || n.id,
        p.path_labels || n.label
    FROM path p
    JOIN graph_edges e
        ON e.source_node_id = p.id
    JOIN graph_nodes n
        ON n.id = e.target_node_id
    WHERE p.depth < 6  -- max depth
      AND NOT n.id = ANY(p.path_ids)  -- avoid cycles
)
SELECT path_labels AS path, depth
FROM path
WHERE id = (
    SELECT id FROM graph_nodes
    WHERE entity_table = 'properties'
      AND entity_id = :target_id
)
ORDER BY depth
LIMIT 1;
```

### Pattern 3: Subgraph Extraction

```python
async def get_deal_subgraph(
    session, deal_id: UUID
) -> dict:
    """Extract the complete subgraph around a deal.

    Returns: deal → property → owner, participants, documents
    """
    query = """
        WITH deal_node AS (
            SELECT id FROM graph_nodes
            WHERE entity_table = 'deals'
              AND entity_id = :deal_id
        ),
        deal_neighborhood AS (
            SELECT DISTINCT n.id, n.node_type, n.label,
                   e.edge_type, e.properties
            FROM deal_node dn
            JOIN graph_edges e
                ON e.source_node_id = dn.id
                OR e.target_node_id = dn.id
            JOIN graph_nodes n
                ON n.id = CASE
                    WHEN e.source_node_id = dn.id
                    THEN e.target_node_id
                    ELSE e.source_node_id
                END
        )
        SELECT * FROM deal_neighborhood
    """
    rows = await session.execute(text(query), {"deal_id": deal_id})
    return {
        "deal": {"id": deal_id},
        "connected_entities": [
            {
                "type": r.node_type,
                "label": r.label,
                "edge": r.edge_type,
                "edge_properties": r.properties,
            }
            for r in rows
        ],
    }
```

### Pattern 4: Aggregation Queries

```sql
-- Centrality: find the most connected clients
SELECT
    n.label,
    n.id,
    COUNT(e.id) AS connection_count,
    AVG(e.weight) AS avg_weight
FROM graph_nodes n
JOIN graph_edges e
    ON e.source_node_id = n.id
    OR e.target_node_id = n.id
WHERE n.node_type = 'client'
GROUP BY n.id, n.label
ORDER BY connection_count DESC
LIMIT 20;

-- Find duplicate-prone clusters
SELECT
    n1.label AS client_a,
    n2.label AS client_b,
    COUNT(*) AS shared_connections
FROM graph_edges e1
JOIN graph_edges e2
    ON e1.target_node_id = e2.target_node_id
    AND e1.source_node_id < e2.source_node_id
JOIN graph_nodes n1 ON n1.id = e1.source_node_id
JOIN graph_nodes n2 ON n2.id = e2.source_node_id
WHERE n1.node_type = 'client'
  AND n2.node_type = 'client'
GROUP BY n1.label, n2.label
HAVING COUNT(*) > 3
ORDER BY shared_connections DESC;

-- Temporal graph: entities that appeared together in documents
SELECT
    DATE_TRUNC('month', n.created_at) AS month,
    n.node_type,
    COUNT(*) AS new_nodes,
    COUNT(DISTINCT e.source_node_id) AS active_entities
FROM graph_nodes n
LEFT JOIN graph_edges e
    ON e.target_node_id = n.id
    AND e.created_at >= DATE_TRUNC('month', n.created_at)
GROUP BY month, n.node_type
ORDER BY month DESC;
```

### Pattern 5: AI-Enhanced Graph Search

```python
class GraphSearch:
    """Semantic search over the knowledge graph using embeddings."""

    async def search(
        self,
        session,
        query: str,
        node_types: list[str] | None = None,
        limit: int = 10,
    ) -> list[GraphNode]:
        """Find nodes semantically similar to the query text."""

        # Generate embedding for query
        query_emb = self.embedder.embed(query)

        sql = """
            SELECT id, node_type, entity_id, label,
                   1 - (embedding <=> :query_emb) AS similarity
            FROM graph_nodes
            WHERE embedding IS NOT NULL
              AND (:node_types IS NULL
                   OR node_type = ANY(:node_types))
            ORDER BY embedding <=> :query_emb
            LIMIT :limit
        """
        rows = await session.execute(text(sql), {
            "query_emb": query_emb,
            "node_types": node_types,
            "limit": limit,
        })
        return [self._to_node(r) for r in rows]

    async def recommend(
        self,
        session,
        entity_type: str,
        entity_id: UUID,
    ) -> list[GraphNode]:
        """Recommend related entities using collaborative filtering
        over the graph structure."""

        # "Clients who are connected to similar entities..."
        sql = """
            WITH my_connections AS (
                -- Entities I'm connected to
                SELECT e.target_node_id
                FROM graph_nodes n
                JOIN graph_edges e ON e.source_node_id = n.id
                WHERE n.entity_table = :entity_table
                  AND n.entity_id = :entity_id
            ),
            similar_entities AS (
                -- Other entities connected to the same things
                SELECT e.source_node_id, COUNT(*) AS common
                FROM graph_edges e
                JOIN my_connections mc
                    ON e.target_node_id = mc.target_node_id
                WHERE e.source_node_id != (
                    SELECT id FROM graph_nodes
                    WHERE entity_table = :entity_table
                      AND entity_id = :entity_id
                )
                GROUP BY e.source_node_id
                ORDER BY common DESC
                LIMIT 5
            )
            SELECT n.id, n.node_type, n.label, se.common
            FROM similar_entities se
            JOIN graph_nodes n ON n.id = se.source_node_id
            ORDER BY se.common DESC
        """
        rows = await session.execute(text(sql), {
            "entity_table": entity_type,
            "entity_id": entity_id,
        })
        return [self._to_node(r) for r in rows]
```

## Graph Maintenance

### Incremental Updates

```sql
-- Trigger: auto-create graph node when entity is inserted
CREATE OR REPLACE FUNCTION create_graph_node()
RETURNS TRIGGER AS $$
DECLARE
    v_node_type node_type;
    v_label TEXT;
BEGIN
    -- Determine node type from table name
    v_node_type := CASE TG_TABLE_NAME
        WHEN 'clients' THEN 'client'
        WHEN 'properties' THEN 'property'
        WHEN 'deals' THEN 'deal'
        WHEN 'documents' THEN 'document'
        WHEN 'communications' THEN 'communication'
        WHEN 'tasks' THEN 'task'
        WHEN 'users' THEN 'user'
        WHEN 'client_contacts' THEN 'client_contact'
        WHEN 'deal_participants' THEN 'deal_participant'
        ELSE 'client'
    END;

    -- Generate human-readable label
    v_label := CASE v_node_type
        WHEN 'client' THEN NEW.full_name
        WHEN 'property' THEN COALESCE(NEW.title, NEW.address)
        WHEN 'deal' THEN COALESCE(NEW.title, 'Deal ' || NEW.id::text)
        WHEN 'document' THEN COALESCE(NEW.title, NEW.file_name)
        WHEN 'communication' THEN LEFT(NEW.content, 100)
        WHEN 'task' THEN NEW.title
        WHEN 'user' THEN NEW.full_name
        ELSE TG_TABLE_NAME || ' ' || NEW.id::text
    END;

    INSERT INTO graph_nodes (node_type, entity_id, entity_table, label)
    VALUES (v_node_type, NEW.id, TG_TABLE_NAME, v_label)
    ON CONFLICT (entity_table, entity_id)
    DO UPDATE SET label = EXCLUDED.label,
                  updated_at = NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to all entity tables
CREATE TRIGGER trg_client_graph_node
    AFTER INSERT OR UPDATE OF full_name ON clients
    FOR EACH ROW EXECUTE FUNCTION create_graph_node();

CREATE TRIGGER trg_property_graph_node
    AFTER INSERT OR UPDATE OF title, address ON properties
    FOR EACH ROW EXECUTE FUNCTION create_graph_node();

CREATE TRIGGER trg_deal_graph_node
    AFTER INSERT OR UPDATE OF title ON deals
    FOR EACH ROW EXECUTE FUNCTION create_graph_node();
-- ... similar triggers for documents, communications, tasks, users
```

### Expiry and Cleanup

```python
class GraphMaintenance:
    """Routine maintenance tasks for the knowledge graph."""

    async def cleanup_expired_edges(self, session):
        """Remove time-bound edges that have expired."""
        await session.execute(text("""
            DELETE FROM graph_edges
            WHERE valid_until IS NOT NULL
              AND valid_until < NOW()
        """))

    async def remove_orphan_nodes(self, session):
        """Remove nodes whose source entities no longer exist."""
        await session.execute(text("""
            DELETE FROM graph_nodes n
            WHERE NOT EXISTS (
                SELECT 1 FROM information_schema.tables t
                WHERE t.table_name = n.entity_table
            ) OR NOT EXISTS (
                SELECT 1 FROM (
                    -- Dynamic table reference via EXECUTE
                    -- Handled by application code
                )
            )
        """))

    async def recompute_embeddings(self, session):
        """Recompute embeddings for nodes with stale or missing embeddings."""
        await session.execute(text("""
            UPDATE graph_nodes
            SET embedding = (
                SELECT pgml.embed(
                    'intfloat/multilingual-e5-small',
                    label
                )
            )
            WHERE embedding IS NULL
               OR updated_at > created_at
        """))

    async def rebuild_fk_edges(self, session):
        """Rebuild FK-derived edges after schema changes or bulk import."""
        builder = FKGraphBuilder()
        for mapping in builder.FK_MAPPINGS:
            await builder._build_fk_edges(session, mapping)
```

## Performance Considerations

| Query Type | Index Strategy | Expected Latency (100K nodes) |
|------------|--------------|------------------------------|
| 1-hop neighborhood | (source_node_id, edge_type) composite | < 5 ms |
| Path finding (≤ 3 hops) | Recursive CTE + indexes | < 50 ms |
| Path finding (≤ 6 hops) | Recursive CTE + indexes | < 500 ms |
| Embedding search | HNSW (ef_search=40) | < 10 ms |
| Aggregation (centrality) | Full scan + GROUP BY | < 1 sec |
| Node label search | GIN trigram index (label) | < 20 ms |

## Future Graph Expansion

### 1. New Node Types
```sql
-- Planned for future releases
ALTER TYPE node_type ADD VALUE 'lead' AFTER 'client';
ALTER TYPE node_type ADD VALUE 'campaign';
ALTER TYPE node_type ADD VALUE 'listing';
ALTER TYPE node_type ADD VALUE 'showing';
ALTER TYPE node_type ADD VALUE 'offer';
```

### 2. New Edge Types
```sql
ALTER TYPE edge_type ADD VALUE 'referred_by';    -- client → client (referral)
ALTER TYPE edge_type ADD VALUE 'similar_to';     -- property → property (similarity)
ALTER TYPE edge_type ADD VALUE 'comparable_to';  -- property → property (price comp)
ALTER TYPE edge_type ADD VALUE 'family_of';      -- client → client
ALTER TYPE edge_type ADD VALUE 'works_at';       -- client → organization
ALTER TYPE edge_type ADD VALUE 'listed_by';      -- property → user (listing agent)
ALTER TYPE edge_type ADD VALUE 'interested_in';  -- client → property (search history)
```

### 3. Materialized Graph Views

```sql
-- Pre-computed subgraphs for common queries
CREATE MATERIALIZED VIEW mv_client_network AS
SELECT
    c.id AS client_id,
    c.full_name AS client_name,
    jsonb_agg(DISTINCT jsonb_build_object(
        'type', n.node_type,
        'label', n.label,
        'relation', e.edge_type
    )) AS network
FROM clients c
JOIN graph_nodes gn ON gn.entity_id = c.id
                    AND gn.entity_table = 'clients'
JOIN graph_edges e ON e.source_node_id = gn.id
JOIN graph_nodes n ON n.id = e.target_node_id
GROUP BY c.id, c.full_name;

CREATE INDEX ON mv_client_network USING GIN (network);
```

### 4. Graph Analytics Functions

```sql
-- Degree centrality
CREATE OR REPLACE FUNCTION graph_degree_centrality(
    p_node_type node_type DEFAULT NULL
)
RETURNS TABLE (
    node_id UUID,
    label VARCHAR,
    degree BIGINT,
    weighted_degree FLOAT
) AS $$
    SELECT
        n.id,
        n.label,
        COUNT(e.id) AS degree,
        COALESCE(SUM(e.weight), 0) AS weighted_degree
    FROM graph_nodes n
    LEFT JOIN graph_edges e
        ON e.source_node_id = n.id
    WHERE (p_node_type IS NULL OR n.node_type = p_node_type)
    GROUP BY n.id, n.label
    ORDER BY degree DESC;
$$ LANGUAGE SQL;

-- Community detection via shared connections
CREATE OR REPLACE FUNCTION graph_shared_connections(
    p_node_id1 UUID,
    p_node_id2 UUID
)
RETURNS TABLE (
    shared_node_id UUID,
    shared_label VARCHAR,
    relation1 edge_type,
    relation2 edge_type
) AS $$
    SELECT
        n.id,
        n.label,
        e1.edge_type AS relation1,
        e2.edge_type AS relation2
    FROM graph_edges e1
    JOIN graph_edges e2
        ON e1.target_node_id = e2.target_node_id
        AND e1.source_node_id = p_node_id1
        AND e2.source_node_id = p_node_id2
    JOIN graph_nodes n ON n.id = e1.target_node_id;
$$ LANGUAGE SQL;
```

## Integration with Document Pipeline

```
Document Upload
    │
    ▼
OCR → Classifier → Extraction → Resolution
    │
    ▼
Knowledge Graph Builder  ←── THIS DOCUMENT
    ├── FK Graph Builder (schema-driven)
    ├── Extraction Graph Builder (document-driven)
    └── AI Edge Builder (inference-driven)
    │
    ▼
Graph Nodes + Edges
    │
    ▼
Query Layer
    ├── Neighborhood (1-hop)
    ├── Path finding (n-hop)
    ├── Subgraph extraction
    ├── Semantic search (embedding)
    └── Recommendations (collaborative)
```

## Related Documentation

- `docs/domain/domain_model.md` — all entity definitions and FK relationships
- `docs/domain/database_schema_v1.md` — underlying database schema
- `docs/architecture/entity_extraction.md` — upstream extraction pipeline
- `docs/architecture/entity_resolution.md` — entity dedup (feeds into graph)
- `docs/development_rules.md` — development guidelines
- `docs/adr/0007-entity-resolution.md` — ADR for resolution strategy
