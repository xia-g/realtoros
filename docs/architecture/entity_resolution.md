# Entity Resolution Subsystem

## Overview

Determines whether entities extracted from documents already exist in the database. Prevents duplicate records and merges new data into existing entities.

```
OCR → Classifier → Entity Extraction → Entity Resolution → DB Insert/Update
                                             │
                                             ▼
                                       (existing entity found)
                                       → update & enrich
                                       → add relationship to document
```

## Entities Requiring Resolution

| Entity | DB Table | Unique Identifiers | Fuzzy Fields | Typical Match Rate |
|--------|----------|-------------------|-------------|-------------------|
| Client | clients | phone, passport, telegram_id, email | full_name, address | 60% existing |
| Property | properties | cadastral_number, address+owner | address, area+rooms | 40% existing |
| Deal | deals | property+clients+dates | price, terms | 20% existing |
| Organization | clients (partner) | inn, ogrn | name | 50% existing |

## Resolution Architecture

### Pipeline

```
Extracted Entity (from Entity Extraction)
    │
    ▼
┌──────────────────────────────────────────────┐
│  Stage 1: Exact Match (blocking)             │
│  (hash lookup, < 1 ms)                       │
│                                              │
│  ├─ Client: phone, passport, telegram_id     │
│  ├─ Property: cadastral_number               │
│  ├─ Organization: INN, OGRN                  │
│  └─ Deal: property_id + client_ids           │
│                                              │
│  Result: exact match → return entity ID      │
│  Result: no exact match → Stage 2            │
└──────────────────────────────────────────────┘
    │ (no exact match)
    ▼
┌──────────────────────────────────────────────┐
│  Stage 2: Fuzzy String Match                 │
│  (trigram similarity + Levenshtein)          │
│                                              │
│  ├─ PG_TRGM for full_name, address           │
│  ├─ Soundex for Russian names                │
│  ├─ Phone normalization + partial match      │
│  └─ Address decomposition + component match  │
│                                              │
│  Result: high confidence → return entity ID  │
│  Result: medium confidence → Stage 3         │
│  Result: low confidence → Stage 3            │
└──────────────────────────────────────────────┘
    │ (ambiguous)
    ▼
┌──────────────────────────────────────────────┐
│  Stage 3: Embedding Similarity               │
│  (pgvector cosine distance)                  │
│                                              │
│  ├─ Client: name + address + role embedding  │
│  ├─ Property: address + type + area embedding│
│  └─ Organization: name + address embedding   │
│                                              │
│  Result: embedding match ≥ 0.85 → confirm    │
│  Result: embedding match < 0.85 → Stage 4    │
└──────────────────────────────────────────────┘
    │ (low confidence)
    ▼
┌──────────────────────────────────────────────┐
│  Stage 4: Review & Merge                     │
│  (confidence scoring + human review)         │
│                                              │
│  ├─ Combine all signals → overall score      │
│  ├─ Score ≥ 0.80 → auto-merge with warning   │
│  ├─ Score 0.50–0.79 → human review           │
│  └─ Score < 0.50 → new entity                │
│                                              │
│  Result: determined → return entity ID       │
│  Result: human review → create task          │
│  Result: new entity → return None            │
└──────────────────────────────────────────────┘
    │
    ▼
Resolved Entity ID (existing UUID) or None (new entity)
```

### Stage 1: Exact Match (Blocking)

Fast deterministic lookup using database unique constraints.

```python
class ExactMatcher:
    """Stage 1: exact field match — blocks most candidates."""

    CLIENT_EXACT_FIELDS = {
        "phone": "phone = :value",
        "passport": (
            "passport_series = :series AND passport_number = :number"
        ),
        "telegram_id": "telegram_id = :value",
        "email": "email = :value",
    }

    PROPERTY_EXACT_FIELDS = {
        "cadastral_number": "cadastral_number = :value",
    }

    ORGANIZATION_EXACT_FIELDS = {
        "inn": "inn = :value",
        "ogrn": "ogrn = :value",
    }

    async def match_client(
        self, session, client: ExtractedClient
    ) -> MatchResult | None:
        """Check each exact field. Return first match with source."""

        checks = [
            ("phone", client.phone),
            ("passport", {
                "series": client.passport_series,
                "number": client.passport_number,
            }),
            ("telegram_id", client.telegram_id),
            ("email", client.email),
        ]

        for field, value in checks:
            if not value:
                continue
            if isinstance(value, dict):
                row = await session.execute(
                    text("""
                        SELECT id, full_name, phone
                        FROM clients
                        WHERE passport_series = :series
                          AND passport_number = :number
                        LIMIT 1
                    """),
                    value,
                )
            else:
                row = await session.execute(
                    text(f"""
                        SELECT id, full_name, phone
                        FROM clients
                        WHERE {self.CLIENT_EXACT_FIELDS[field]}
                        LIMIT 1
                    """),
                    {"value": value},
                )
            found = row.fetchone()
            if found:
                return MatchResult(
                    matched_id=found[0],
                    method="exact",
                    match_field=field,
                    confidence=0.99,
                )

        return None  # no exact match, proceed to Stage 2
```

**Coverage:** ~40% of entities resolved at Stage 1 (phone and passport are common).

### Stage 2: Fuzzy String Match

Uses PostgreSQL trigram similarity (`pg_trgm`) and Levenshtein distance for approximate matching.

```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;

-- Trigram indexes for fuzzy search
CREATE INDEX idx_clients_full_name_trgm
    ON clients USING GIN (full_name gin_trgm_ops);

CREATE INDEX idx_properties_address_trgm
    ON properties USING GIN (address gin_trgm_ops);
```

```python
class FuzzyMatcher:
    """Stage 2: fuzzy string matching using pg_trgm."""

    SIMILARITY_THRESHOLD = 0.6   # pg_trgm similarity
    LEVENSHTEIN_MAX = 3          # max edit distance for names

    CLIENT_BLOCKING_QUERY = """
        SELECT id, full_name, phone, email,
               similarity(full_name, :query_name) AS name_sim
        FROM clients
        WHERE full_name % :query_name         -- pg_trgm index condition
           OR phone = :query_phone
           OR email = :query_email
        ORDER BY name_sim DESC
        LIMIT 10
    """

    PROPERTY_FUZZY_QUERY = """
        SELECT id, address, cadastral_number,
               similarity(address, :query_address) AS addr_sim
        FROM properties
        WHERE address % :query_address
        ORDER BY addr_sim DESC
        LIMIT 10
    """

    def score_name(self, extracted: str, existing: str) -> float:
        """
        Russian name similarity scoring.
        Handles: Иванов Иван Иванович vs Иванов И.И.
                 Петров Пётр vs Петров Петр (ё/е)
                 Смирнова vs Смирнов (gender variants)
        """
        # Normalize: lowercase, ё→е, strip patronymic for comparison
        def norm(name: str) -> str:
            name = name.lower().replace("ё", "е")
            parts = name.split()
            # Return all parts (first + last name minimum)
            return " ".join(parts[:2])  # first 2 parts (surname + given)

        extracted_norm = norm(extracted)
        existing_norm = norm(existing)

        # 1. Exact match after normalization
        if extracted_norm == existing_norm:
            return 0.95

        # 2. Trigram similarity
        trgm_sim = self._trgm_similarity(extracted_norm, existing_norm)
        if trgm_sim >= 0.8:
            return trgm_sim

        # 3. Levenshtein on surname only
        ext_surname = self._extract_surname(extracted)
        exist_surname = self._extract_surname(existing)
        if ext_surname and exist_surname:
            dist = self._levenshtein(ext_surname, exist_surname)
            if dist <= 1:
                return 0.85
            if dist <= 2:
                return 0.70

        # 4. Soundex (phonetic matching for Russian names)
        # Иванов → Иванна (same soundex cluster)
        if self._russian_soundex(ext_surname) == \
           self._russian_soundex(exist_surname):
            return 0.60

        return trgm_sim  # fallback to trigram

    def score_address(self, extracted: str, existing: str) -> float:
        """
        Russian address similarity.
        Handles: ул. Ленина vs улица Ленина
                 г. Москва vs город Москва
                 д. 5 vs дом 5
        """
        def normalize_address(addr: str) -> str:
            replacements = {
                r"\bг\.?\b": "город",
                r"\bул\.?\b": "улица",
                r"\bд\.?\b": "дом",
                r"\bкв\.?\b": "квартира",
                r"\bстр\.?\b": "строение",
                r"\bкорп\.?\b": "корпус",
                r"\bобл\.?\b": "область",
                r"\bр\-н\b": "район",
                r"\bпл\.?\b": "площадь",
                r"\bпр\-т\b": "проспект",
                r"\bбульв\.?\b": "бульвар",
            }
            result = addr.lower().replace("ё", "е")
            for pattern, replacement in replacements.items():
                result = re.sub(pattern, replacement, result)
            return result.strip()

        return self._trgm_similarity(
            normalize_address(extracted),
            normalize_address(existing),
        )

    async def match_client(
        self, session, client: ExtractedClient
    ) -> list[MatchResult]:
        """Find candidate clients by fuzzy matching."""

        candidates = await session.execute(
            text(self.CLIENT_BLOCKING_QUERY),
            {
                "query_name": client.full_name,
                "query_phone": client.phone or "",
                "query_email": client.email or "",
            },
        )
        results = []
        for row in candidates:
            name_score = self.score_name(client.full_name, row.full_name)
            if name_score >= 0.60:
                results.append(MatchResult(
                    matched_id=row.id,
                    method="fuzzy_name",
                    confidence=name_score,
                    details={
                        "name_similarity": name_score,
                        "existing_name": row.full_name,
                        "existing_phone": row.phone,
                    },
                ))
        return results
```

### Stage 3: Embedding Similarity

Uses pgvector with cosine distance for semantic matching of names, addresses, and entity descriptions.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding columns
ALTER TABLE clients ADD COLUMN embedding vector(384);
ALTER TABLE properties ADD COLUMN embedding vector(384);
ALTER TABLE clients ADD COLUMN name_embedding vector(384);

-- HNSW indexes for fast approximate nearest neighbor search
CREATE INDEX idx_clients_embedding
    ON clients USING hnsw (embedding vector_cosine_ops);

CREATE INDEX idx_properties_embedding
    ON properties USING hnsw (embedding vector_cosine_ops);
```

```python
class EmbeddingMatcher:
    """Stage 3: semantic similarity using pgvector.

    Uses a lightweight sentence-transformer model for embeddings.
    Model: paraphrazie-ru-bert-mini or intfloat/multilingual-e5-small
    Output: 384-dimensional vectors
    """

    def __init__(self):
        from sentence_transformers import SentenceTransformer
        model_name = "intfloat/multilingual-e5-small"  # 384d, multilingual
        self.model = SentenceTransformer(model_name)
        self.batch_size = 32

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a text string."""
        # e5 models require 'query: ' prefix for queries
        return self.model.encode(
            f"query: {text}",
            normalize_embeddings=True,
        ).tolist()

    def embed_batch(
        self, texts: list[str]
    ) -> list[list[float]]:
        """Batch embedding generation."""
        prefixed = [f"query: {t}" for t in texts]
        embeddings = self.model.encode(
            prefixed,
            normalize_embeddings=True,
            batch_size=self.batch_size,
        )
        return embeddings.tolist()

    async def match_client(
        self, session, client: ExtractedClient
    ) -> list[MatchResult]:
        """Find similar clients by embedding cosine distance."""

        query_text = f"{client.full_name} {' '.join(client.tags or [])}"
        embedding = self.embed(query_text)

        # pgvector ANN search via HNSW index
        rows = await session.execute(
            text("""
                SELECT id, full_name, phone,
                       1 - (embedding <=> :query_emb) AS cosine_sim
                FROM clients
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> :query_emb
                LIMIT 5
            """),
            {"query_emb": embedding},
        )

        results = []
        for row in rows:
            if row.cosine_sim >= 0.80:
                results.append(MatchResult(
                    matched_id=row.id,
                    method="embedding",
                    confidence=row.cosine_sim,
                    details={"cosine_similarity": row.cosine_sim},
                ))
        return results
```

**Embedding computation triggers:**

1. **On entity creation:** compute and store embedding for new records
2. **On entity update:** recompute embedding if name/address changed
3. **Batch re-index:** nightly job to update embeddings for modified records

```sql
-- Trigger function for automatic embedding updates
CREATE OR REPLACE FUNCTION update_client_embedding()
RETURNS TRIGGER AS $$
BEGIN
    NEW.embedding = (
        SELECT pgml.embed(
            'intfloat/multilingual-e5-small',
            CONCAT(NEW.full_name, ' ', COALESCE(NEW.notes, ''))
        )
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_client_embedding
    BEFORE INSERT OR UPDATE OF full_name, notes
    ON clients
    FOR EACH ROW
    EXECUTE FUNCTION update_client_embedding();
```

Note: If `pgml` extension is not available, embeddings are computed in Python and stored via SQLAlchemy.

### Stage 4: Review & Merge — Confidence Scoring

Combines all signals into a unified resolution decision.

```python
class ResolutionScorer:
    """Computes overall resolution confidence from all signals."""

    # Weight for each signal type
    SIGNAL_WEIGHTS = {
        "exact_phone": 1.0,
        "exact_passport": 1.0,
        "exact_telegram": 1.0,
        "exact_email": 0.95,
        "exact_inn": 1.0,
        "exact_cadastral": 1.0,
        "fuzzy_name_high": 0.85,    # trigram ≥ 0.8
        "fuzzy_name_medium": 0.70,  # trigram 0.6–0.8
        "fuzzy_address_high": 0.80,
        "fuzzy_address_medium": 0.60,
        "embedding_high": 0.90,     # cosine ≥ 0.9
        "embedding_medium": 0.75,   # cosine 0.8–0.9
        "phone_match_weak": 0.50,   # partial phone match
        "name_initials": 0.65,      # Иванов И.И. vs Иванов Иван Иванович
    }

    # Category thresholds
    THRESHOLDS = {
        "auto_merge": 0.85,      # merge without human
        "auto_merge_warn": 0.75, # merge with system note
        "human_review": 0.50,    # send to operator
        "new_entity": 0.0,       # create new record
    }

    def compute_score(
        self, signals: list[MatchSignal]
    ) -> ResolutionDecision:
        """
        Combine multiple match signals into one decision.

        Signals are independent match attempts:
        - phone exact match → weight 1.0
        - name fuzzy 0.85 → weight 0.85
        - embedding 0.92 → weight 0.90
        """

        if not signals:
            return ResolutionDecision(
                decision="new_entity",
                confidence=0.0,
                signals=[],
            )

        # Multiple high-confidence signals → very confident
        high_signals = [s for s in signals if s.weight >= 0.80]
        if len(high_signals) >= 2:
            # Two strong independent signals (e.g., phone + name)
            combined = 1.0 - (1.0 - high_signals[0].weight) * \
                             (1.0 - high_signals[1].weight)
            combined = min(combined + 0.05, 0.99)
        else:
            # Best single signal
            combined = max(s.weight for s in signals)

        # Penalty: conflicting signals
        # e.g., phone matches Client A but name matches Client B
        unique_ids = set(s.matched_id for s in signals)
        if len(unique_ids) > 1:
            combined = max(combined - 0.20, 0.0)

        # Determine action
        if combined >= self.THRESHOLDS["auto_merge"]:
            decision = "auto_merge"
        elif combined >= self.THRESHOLDS["auto_merge_warn"]:
            decision = "auto_merge_warn"
        elif combined >= self.THRESHOLDS["human_review"]:
            decision = "human_review"
        else:
            decision = "new_entity"

        return ResolutionDecision(
            decision=decision,
            confidence=round(combined, 3),
            matched_id=list(unique_ids)[0] if len(unique_ids) == 1 else None,
            signals=signals,
        )
```

## Entity-Specific Resolution Rules

### 1. Client Resolution

```python
CLIENT_RESOLUTION_RULES = {
    "required_create": ["full_name"],  # minimum to create
    "required_match": ["full_name"],   # minimum to confirm match

    "unique_fields": [
        "phone",
        "passport_series + passport_number",
        "telegram_id",
        "email",
    ],

    "resolution_fields": {
        "full_name": {
            "weight": 0.35,
            "method": "fuzzy_name",
            "threshold": 0.60,
        },
        "phone": {
            "weight": 0.30,
            "method": "exact",
            "threshold": 1.0,
        },
        "passport": {
            "weight": 0.25,
            "method": "exact",
            "threshold": 1.0,
        },
        "email": {
            "weight": 0.20,
            "method": "exact",
            "threshold": 1.0,
        },
        "registration_address": {
            "weight": 0.15,
            "method": "fuzzy_address",
            "threshold": 0.60,
        },
        "birth_date": {
            "weight": 0.20,
            "method": "exact",
            "threshold": 1.0,
        },
        "telegram_id": {
            "weight": 0.25,
            "method": "exact",
            "threshold": 1.0,
        },
    },

    "merge_strategy": {
        "strategy": "enrich",  # never overwrite, only fill missing fields
        "fields": {
            "phone": "fill_if_missing",
            "email": "fill_if_missing",
            "telegram_id": "fill_if_missing",
            "notes": "append",  # append new source info
            "tags": "union",    # merge tag arrays
            "source": "keep_original",
        },
    },
}
```

#### Client Resolution Examples

| Extracted | Existing DB | Match Method | Confidence | Decision |
|-----------|-------------|-------------|------------|----------|
| +79161234567 | phone: +79161234567 | exact phone | 1.0 | auto_merge |
| 4516 123456 | passport: 4516 123456 | exact passport | 1.0 | auto_merge |
| Иванов Иван | Иванов Иван Иванович | fuzzy name 0.92 | 0.85 | auto_merge |
| Иванов Иван | Петров Пётр | fuzzy name 0.25 | < 0.50 | new_entity |
| +79161234567 + Иванов | phone match A, name match B | conflicting signals | 0.65 | human_review |
| Иванoв (latn) | Иванов (cyrillic) | embedding 0.88 | 0.75 | auto_merge_warn |

### 2. Property Resolution

```python
PROPERTY_RESOLUTION_RULES = {
    "required_create": ["address", "property_type"],
    "required_match": ["cadastral_number"],

    "unique_fields": ["cadastral_number"],

    "resolution_fields": {
        "cadastral_number": {
            "weight": 0.40,
            "method": "exact",
            "threshold": 1.0,
        },
        "address": {
            "weight": 0.30,
            "method": "fuzzy_address + embedding",
            "threshold": 0.65,
        },
        "area_total": {
            "weight": 0.15,
            "method": "numeric_tolerance",
            "tolerance": 0.05,  # 5% difference allowed
        },
        "rooms": {
            "weight": 0.10,
            "method": "exact",
            "threshold": 1.0,
        },
        "owner_id": {
            "weight": 0.15,
            "method": "client_match",
        },
    },

    "merge_strategy": {
        "strategy": "enrich",
        "fields": {
            "area_total": "verify_consistency",
            "area_living": "verify_consistency",
            "rooms": "verify_consistency",
            "floor": "fill_if_missing",
            "notes": "append",
            "photos": "union",
            "documents": "union",
        },
    },
}
```

#### Property Resolution Examples

| Extracted | Existing DB | Match Method | Confidence | Decision |
|-----------|-------------|-------------|------------|----------|
| 77:01:0004545:1234 | cadastral 77:01:0004545:1234 | exact cadastral | 1.0 | auto_merge |
| ул. Ленина, д. 5, кв. 10 | Ленина 5-10 | fuzzy address 0.82 | 0.80 | auto_merge |
| 54.2 m², 2 rooms | 54.0 m², 2 rooms | area 0.99 + rooms exact | 0.88 | auto_merge |
| ЖК Солнечный | no match | embedding 0.45 | < 0.50 | new_entity |
| ул. Ленина 10 + 54.2 m² | Ленина 5 (23 m²) | address match but area mismatch | 0.55 | human_review |

### 3. Deal Resolution

```python
DEAL_RESOLUTION_RULES = {
    "required_create": ["property_id"],
    "required_match": ["property_id", "deal_type"],

    "unique_fields": [],  # no single unique field for deals

    "resolution_fields": {
        "property_id": {
            "weight": 0.30,
            "method": "exact",
        },
        "seller_id + buyer_id": {
            "weight": 0.25,
            "method": "exact_client_ids",
        },
        "start_date": {
            "weight": 0.15,
            "method": "exact_date",
            "tolerance_days": 7,
        },
        "price": {
            "weight": 0.15,
            "method": "numeric_tolerance",
            "tolerance": 0.10,  # 10% difference allowed
        },
        "deal_type": {
            "weight": 0.15,
            "method": "exact",
            "threshold": 1.0,
        },
    },

    "merge_strategy": {
        "strategy": "no_automerge",  # deals are too sensitive
        "fields": {},  # all deal updates require human review
    },
}
```

#### Deal Resolution Examples

| Extracted | Existing DB | Match Method | Confidence | Decision |
|-----------|-------------|-------------|------------|----------|
| prop X, client A+B, 01.06.2026 | same | exact composite | 0.95 | auto_merge_warn |
| prop X, client A, 01.06.2026 | prop X, client A+B, 05.06.2026 | partial match | 0.70 | human_review |
| prop X, different clients | prop X, different clients | property match only | 0.30 | new_entity |

## Merge & Update Logic

```python
class EntityMerger:
    """Merges extracted data into existing entities."""

    def merge_client(
        self,
        session,
        existing_id: UUID,
        extracted: ExtractedClient,
        decision: ResolutionDecision,
    ) -> Client:
        """Merge extracted client data into existing record."""

        existing = await session.get(Client, existing_id)
        strategy = CLIENT_RESOLUTION_RULES["merge_strategy"]

        changes = {}
        for field, action in strategy["fields"].items():
            extracted_value = getattr(extracted, field, None)
            existing_value = getattr(existing, field, None)

            if not extracted_value:
                continue

            if action == "fill_if_missing" and existing_value is None:
                changes[field] = extracted_value
                changes[f"source_{field}"] = "document_extraction"

            elif action == "append":
                existing_notes = existing_value or ""
                changes[field] = f"{existing_notes}\n[Из документа] {extracted_value}"

            elif action == "union":
                # Merge arrays, deduplicate
                existing_tags = set(existing_value or [])
                new_tags = set(extracted.tags or [])
                changes[field] = list(existing_tags | new_tags)

            elif action == "verify_consistency":
                if existing_value and extracted_value:
                    diff = abs(existing_value - extracted_value) / max(existing_value, 0.01)
                    if diff > 0.05:
                        decision.add_warning(
                            f"Поле '{field}' различается: "
                            f"{existing_value} (БД) vs {extracted_value} (документ)"
                        )

        # Add document link
        changes.setdefault("notes", "")
        changes["notes"] += (
            f"\n[Документ {extracted.document_id}] "
            f"Обновлено {datetime.utcnow().isoformat()}"
        )

        if changes and decision.decision in ("auto_merge", "auto_merge_warn"):
            for field, value in changes.items():
                setattr(existing, field, value)
            await session.flush()

        return existing

    def create_new_client(
        self,
        session,
        extracted: ExtractedClient,
    ) -> Client:
        """Create new client record from extracted data."""
        client = Client(
            full_name=extracted.full_name,
            phone=extracted.phone,
            email=extracted.email,
            # Only set fields with confidence > 0.80
            **{k: v for k, v in extracted.filtered_fields(threshold=0.80).items()},
        )
        session.add(client)
        return client
```

### Merge Conflict Resolution

```python
MERGE_CONFLICT_RULES = {
    # When both DB and extraction have values for the same field
    "strategy": "prefer_higher_confidence",
    "overrides": {
        # Fields that should never be overwritten
        "immutable": ["created_at", "id", "type"],
        # Fields where DB value always wins
        "db_wins": ["status", "source"],
        # Fields where new value always wins (if higher confidence)
        "new_wins_if_confident": ["phone", "email", "telegram_id"],
    },
    "conflict_resolution": {
        "conflicting_phones": {
            "action": "keep_both",  # add as secondary contact
            "note": "Обнаружен второй телефон: {new}",
        },
        "conflicting_names": {
            "action": "human_review",
            "note": "Разные ФИО для одного клиента: {db} vs {new}",
        },
    },
}
```

## Database Schema

### New Tables

```sql
-- Entity resolution result linking extraction to existing entities
CREATE TABLE entity_resolutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extracted_entity_id UUID NOT NULL REFERENCES extracted_entities(id) ON DELETE CASCADE,

    -- Resolved target
    resolved_entity_type VARCHAR(20) NOT NULL,  -- client, property, deal, organization
    resolved_entity_id UUID,                     -- NULL = new entity
    resolved_entity_label VARCHAR(255),          -- human-readable label

    -- Decision
    decision VARCHAR(20) NOT NULL,  -- auto_merge, auto_merge_warn, human_review, new_entity
    overall_confidence FLOAT NOT NULL DEFAULT 0.0,

    -- Match signals
    match_signals JSONB NOT NULL DEFAULT '[]',
    -- [{"method": "exact_phone", "confidence": 1.0, "matched_id": "uuid"}]

    -- Merge audit
    merge_log JSONB DEFAULT '[]',
    -- [{"field": "phone", "action": "fill_if_missing", "old": null, "new": "+79161234567"}]

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending | applied | skipped | rejected

    -- Human review
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,
    review_decision VARCHAR(20),  -- confirm, reject, modify

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_decision CHECK (
        decision IN ('auto_merge', 'auto_merge_warn',
                     'human_review', 'new_entity')
    ),
    CONSTRAINT valid_status CHECK (
        status IN ('pending', 'applied', 'skipped', 'rejected')
    ),
    CONSTRAINT valid_review CHECK (
        review_decision IN ('confirm', 'reject', 'modify')
    )
);

-- Entity embeddings
CREATE TABLE entity_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(20) NOT NULL,
    entity_id UUID NOT NULL,
    embedding vector(384) NOT NULL,
    model_version VARCHAR(50) NOT NULL DEFAULT 'multilingual-e5-small-v1',
    text_hash VARCHAR(64) NOT NULL,  -- SHA-256 of source text (dedup)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (entity_type, entity_id, model_version)
);

-- Human review queue
CREATE TABLE resolution_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_resolution_id UUID NOT NULL REFERENCES entity_resolutions(id),

    -- What the operator sees
    extracted_data JSONB NOT NULL,          -- from extraction
    candidates JSONB NOT NULL DEFAULT '[]',  -- top matching candidates
    -- [{"id": "uuid", "name": "Иванов Иван", "confidence": 0.85, "fields": {...}}]

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    assigned_to UUID REFERENCES users(id),
    priority VARCHAR(10) DEFAULT 'medium',
    notified_at TIMESTAMPTZ,     -- Telegram notification sent
    responded_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_review_status CHECK (
        status IN ('pending', 'assigned', 'resolved', 'expired')
    )
);

-- Indexes
CREATE INDEX idx_entity_resolutions_extracted
    ON entity_resolutions(extracted_entity_id);
CREATE INDEX idx_entity_resolutions_decision
    ON entity_resolutions(decision);
CREATE INDEX idx_entity_resolutions_status
    ON entity_resolutions(status);
CREATE INDEX idx_resolution_reviews_status
    ON resolution_reviews(status);
CREATE INDEX idx_resolution_reviews_assigned
    ON resolution_reviews(assigned_to);
```

### Schema Changes to Existing Tables

```sql
-- Add embedding columns for similarity search
ALTER TABLE clients ADD COLUMN IF NOT EXISTS
    name_embedding vector(384);
ALTER TABLE clients ADD COLUMN IF NOT EXISTS
    embedding vector(384);

ALTER TABLE properties ADD COLUMN IF NOT EXISTS
    embedding vector(384);

-- HNSW indexes for fast ANN search
CREATE INDEX IF NOT EXISTS idx_clients_name_embedding
    ON clients USING hnsw (name_embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_clients_embedding
    ON clients USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_properties_embedding
    ON properties USING hnsw (embedding vector_cosine_ops);
```

## Human Review Workflow

```python
class HumanReviewWorkflow:
    """Manages human review queue for entity resolution."""

    async def create_review_task(
        self,
        resolution: ResolutionDecision,
        extracted: ExtractedEntity,
        candidates: list[MatchResult],
    ) -> ResolutionReview:
        """Create a human review task with Telegram notification."""

        review = ResolutionReview(
            entity_resolution_id=resolution.id,
            extracted_data=extracted.model_dump(),
            candidates=[
                {
                    "id": c.matched_id,
                    "confidence": c.confidence,
                    "method": c.method,
                    "fields": c.details,
                }
                for c in candidates[:5]  # top 5 candidates
            ],
            status="pending",
        )
        session.add(review)
        await session.flush()

        # Notify agent via Telegram
        await self._send_telegram_notification(review)

        return review

    async def resolve_review(
        self,
        review_id: UUID,
        decision: str,  # confirm_match, new_entity, modify
        operator_id: UUID,
        modifications: dict | None = None,
    ) -> EntityResolution:
        """Process operator's decision."""
        review = await session.get(ResolutionReview, review_id)
        resolution = await session.get(
            EntityResolution, review.entity_resolution_id
        )

        if decision == "confirm_match":
            resolution.decision = "auto_merge"
            resolution.status = "applied"
            # Apply merge
            await merger.merge_client(session, resolution.resolved_entity_id, ...)

        elif decision == "new_entity":
            resolution.decision = "new_entity"
            resolution.status = "applied"
            # Create new entity
            await merger.create_new_client(session, ...)

        elif decision == "modify":
            # Operator corrected the extracted data
            for field, value in (modifications or {}).items():
                setattr(extracted_data, field, value)
            resolution.status = "applied"

        resolution.reviewed_by = operator_id
        resolution.reviewed_at = datetime.utcnow()
        review.status = "resolved"
        review.responded_at = datetime.utcnow()

        return resolution

    async def _send_telegram_notification(
        self, review: ResolutionReview
    ) -> None:
        """Send inline keyboard with candidates to operator."""
        message = (
            f"📄 *Требуется проверка*\n\n"
            f"Извлечено из документа:\n"
            f"`{self._format_entity(review.extracted_data)}`\n\n"
            f"*Кандидаты на слияние:*\n"
        )
        for i, c in enumerate(review.candidates, 1):
            message += (
                f"\n{i}. {c['fields'].get('existing_name', '—')} "
                f"(точность: {c['confidence']:.0%}, {c['method']})"
            )

        # Create inline keyboard
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        f"✅ #{i}",
                        callback_data=f"resolve:{review.id}:match:{c['id']}",
                    )
                ]
                for i, c in enumerate(review.candidates, 1)
            ] + [
                [
                    InlineKeyboardButton(
                        "➕ Новый", callback_data=f"resolve:{review.id}:new"
                    ),
                    InlineKeyboardButton(
                        "✏️ Изменить",
                        callback_data=f"resolve:{review.id}:modify",
                    ),
                ]
            ]
        )

        await telegram_bot.send_message(
            chat_id=settings.REVIEW_GROUP_CHAT_ID,
            text=message,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
```

## Performance Targets

| Metric | Target |
|--------|--------|
| Stage 1 (exact) latency | < 1 ms per entity |
| Stage 2 (fuzzy) latency | < 10 ms per entity |
| Stage 3 (embedding) latency | < 50 ms per entity |
| End-to-end resolution | < 200 ms per entity |
| Auto-resolution rate | > 80% (auto_merge + auto_merge_warn) |
| Human review rate | < 20% of extractions |
| Duplicate prevention rate | > 99% |
| False match rate | < 0.5% |

## Error Handling

| Failure Mode | Handler |
|--------------|---------|
| pgvector not installed | Fall back to fuzzy-only matching |
| Embedding model unavailable | Use cached embeddings; compute async |
| Conflicting matches (phone→A, name→B) | Flag for human review, do not auto-merge |
| Merge fails (constraint violation) | Log error, flag extraction for human review |
| Multiple candidates at same confidence | Show all to operator in review queue |
| Entity deleted after resolution started | Skip, log warning, mark extraction for re-processing |

## Related Documentation

- `docs/architecture/entity_extraction.md` — upstream extraction pipeline
- `docs/domain/domain_model.md` — core entities being resolved
- `docs/domain/database_schema_v1.md` — database schema with embedding columns
- `docs/development_rules.md` — AI model selection guidelines
- `docs/adr/0006-entity-extraction.md` — ADR for extraction strategy
