# Sprint 1.5 — AI Foundation

**Goal:** AI infrastructure layer supporting all downstream AI features (Knowledge Agent, Lead Scoring, Entity Resolution).

**Prerequisites:** Sprint 1 complete (configuration, database, models, migrations, error handling, logging).

**Duration:** 4 days
**Scope:** pgvector, embedding service, AI router, model registry, cost tracking, token accounting, provider fallback.

**No document pipeline, no lead scoring, no business logic. Infrastructure only.**

---

## Current State

### What Exists

| Artifact | State | Note |
|----------|-------|------|
| `ai/` directory | Empty stubs | `agents/`, `embeddings/`, `extractors/`, `prompts/` — no `.py` files |
| `backend/config.py` | Has AI settings | `AI_QWEN_ENDPOINT`, `AI_DEEPSEEK_FLASH`, `AI_PRO`, `AI_CHATGPT_API_KEY`, `AI_EMBEDDING_MODEL` |
| `backend/database.py` | Async engine | No pgvector extension |
| PostgreSQL 17 | Installed | pgvector 0.8.0 already installed (from `pg_lsclusters`) |
| `docs/development_rules.md` | AI model tiers | Qwen (simple), DeepSeek Flash (medium), DeepSeek Pro (complex), ChatGPT (critical) |

### What Is Missing

| Artifact | Priority | Reason |
|----------|----------|--------|
| pgvector migration | Critical | Needed for embedding columns and ANN search |
| Embedding service | Critical | Core AI primitive — entity resolution, semantic search |
| AI Router | Critical | All Knowledge Agent stages depend on it |
| Model registry | High | Provider discovery, capability mapping |
| Cost tracker | High | Budget control, provider cost comparison |
| Token accounting | High | Input/output tracking per request |
| Provider fallback | High | Resilience when primary provider fails |
| AI config section | Medium | Per-model endpoints, rate limits, timeouts |

---

## Task Breakdown

Total: **56 hours = 7 person-days**

### Phase 1: pgvector + Embedding — Day 1 (16h)

#### T1: pgvector Database Integration (6h)

**Files:**
- `backend/migrations/versions/003_add_pgvector.py` — NEW
- `ai/embeddings/__init__.py` — NEW

**Acceptance Criteria:**
- Migration creates `vector` extension
- Migration adds `embedding vector(384)` column to `clients` and `properties`
- Migration adds `name_embedding vector(384)` to `clients`
- Migration creates HNSW indexes (ef_construction=64, m=16):
  ```sql
  CREATE INDEX idx_clients_embedding ON clients
    USING hnsw (embedding vector_cosine_ops)
    WITH (ef_construction=64, m=16);
  CREATE INDEX idx_clients_name_embedding ON clients
    USING hnsw (name_embedding vector_cosine_ops)
    WITH (ef_construction=64, m=16);
  CREATE INDEX idx_properties_embedding ON properties
    USING hnsw (embedding vector_cosine_ops)
    WITH (ef_construction=64, m=16);
  ```
- Migration is idempotent: `CREATE EXTENSION IF NOT EXISTS vector`
- `alembic upgrade head` succeeds
- `alembic downgrade -1` drops indexes + columns + extension

**Verification:**
```python
# psql: SELECT extname FROM pg_extension; → vector
# psql: \d clients → shows embedding vector(384)
```

#### T2: Embedding Model Service (6h)

**Files:**
- `ai/embeddings/embedder.py` — NEW

**Acceptance Criteria:**
- `EmbeddingService` class:
  - Loads `intfloat/multilingual-e5-small` (384d) via `sentence-transformers`
  - Method: `async def embed(text: str) -> list[float]`
  - Method: `async def embed_batch(texts: list[str]) -> list[list[float]]`
  - Method: `async def embed_entity(entity_type: str, entity_id: UUID) -> list[float]`
  - Method: `async def similarity(a: list[float], b: list[float]) -> float`
- e5 models require `query: ` or `passage: ` prefix:
  - `embed(text)` uses `query: {text}` prefix
  - `embed_batch(texts)` uses `query: ` prefix for each
  - `embed_entity(entity_type, entity_id)` reads entity from DB, constructs text: `"{full_name} {notes}"` for clients, `"{address} {description}"` for properties, uses `passage: ` prefix
- Batch processing with configurable batch size (default 32)
- Normalized embeddings (`normalize_embeddings=True`)
- Model loaded lazily on first call (not at import time)
- GPU support if available (`.to('cuda')`), falls back to CPU
- Caching: in-memory LRU cache for frequently accessed embeddings (max 1000 entries, TTL 5 minutes)
- `from ai.embeddings.embedder import embedder` works

**Error handling:**
- Model load failure → `EmbeddingModelError` with clear message
- Batch OOM → automatic batch size halving and retry
- Empty input → return zero vector (not an error)
- Timeout > 30s → raise `EmbeddingTimeoutError`

**Performance targets:**
- Single embedding: < 50 ms (CPU), < 10 ms (GPU)
- Batch of 32: < 500 ms (CPU), < 100 ms (GPU)
- Cache hit: < 1 ms

#### T3: Embedding Storage Service (4h)

**Files:**
- `ai/embeddings/storage.py` — NEW

**Acceptance Criteria:**
- `EmbeddingStorage` class:
  - `async def store(entity_type, entity_id, embedding)` — UPDATE entity table
  - `async def get(entity_type, entity_id)` — read embedding from entity table
  - `async def search_similar(entity_type, query_embedding, limit=10, threshold=0.7)` — ANN search via HNSW:
    ```sql
    SELECT id, 1 - (embedding <=> :query) AS similarity
    FROM {table}
    WHERE embedding IS NOT NULL
      AND 1 - (embedding <=> :query) >= :threshold
    ORDER BY embedding <=> :query
    LIMIT :limit
    ```
  - `async def recompute_stale(entity_type, max_age_hours=24)` — find entities with NULL or outdated embeddings
- Does NOT call the embedding model — only reads/writes vectors in DB
- Works with `AsyncSession` passed from caller
- Entity table mapping: `{"client": "clients", "property": "properties"}`

---

### Phase 2: AI Router — Day 2 (16h)

#### T4: Provider Registry (6h)

**Files:**
- `ai/router.py` — NEW

**Acceptance Criteria:**
- `ModelProvider` dataclass:
  ```python
  @dataclass
  class ModelProvider:
      name: str                           # "qwen-local", "deepseek-flash", etc.
      display_name: str                   # "Qwen 2.5 (Local)"
      provider_type: Literal["openai", "openrouter", "local", "custom"]
      base_url: str | None                # API endpoint
      api_key_env: str | None             # env var name
      models: list[str]                   # model names this provider serves
      capabilities: set[str]              # {"chat", "json_mode", "function_calling", "vision"}
      max_tokens: int                     # max output tokens
      max_input_tokens: int               # max input context
      cost_per_1k_input: Decimal           # USD
      cost_per_1k_output: Decimal          # USD
      rate_limit_rpm: int                  # requests per minute
      rate_limit_tpm: int                  # tokens per minute
      timeout_seconds: int
  ```
- `PROVIDER_REGISTRY` constant dict with all 5 providers configured:
  - `qwen-local`: provider_type=local, base_url from settings, max_tokens=4096, cost=0
  - `deepseek-flash`: provider_type=openrouter, max_tokens=8192, cost_per_1k_input=0.0001
  - `deepseek-pro`: provider_type=openrouter, max_tokens=16384, cost_per_1k_input=0.0005
  - `glm-flash`: provider_type=openrouter, max_tokens=8192, cost_per_1k_input=0.00005
  - `openai`: provider_type=openai, max_tokens=16384, cost_per_1k_input=0.0025
- `ModelRegistry` class:
  - `get_provider(model_name: str) -> ModelProvider | None`
  - `get_capable_models(capability: str) -> list[tuple[str, ModelProvider]]`
  - `get_cheapest_model(task_complexity: str) -> str` — returns cheapest capable model
  - `get_all_providers() -> dict[str, ModelProvider]`
- All cost values are configurable via settings (with defaults)
- Registration is data-driven, no hardcoded if/else chains

#### T5: AI Router Core (6h)

**Files:**
- `ai/router.py` — continues from T4

**Acceptance Criteria:**
- `AIRouter` class:
  - `ROUTING_TABLE` — maps task types to model configurations:
    ```python
    ROUTING_TABLE = {
        "classify_llm": {
            "primary": "deepseek-flash",
            "fallback": ["deepseek-pro", "chatgpt"],
            "capabilities": ["json_mode"],
            "timeout": 15,
        },
        "extract_passport": {
            "primary": "qwen-local",
            "fallback": ["deepseek-flash"],
            "capabilities": ["json_mode"],
            "timeout": 10,
        },
        "extract_contract": {
            "primary": "deepseek-pro",
            "fallback": ["chatgpt"],
            "capabilities": ["json_mode"],
            "timeout": 30,
        },
        "extract_receipt": {
            "primary": "qwen-local",
            "fallback": ["deepseek-flash"],
            "capabilities": ["json_mode"],
            "timeout": 10,
        },
        "extract_egrn": {
            "primary": "deepseek-flash",
            "fallback": ["deepseek-pro"],
            "capabilities": ["json_mode"],
            "timeout": 15,
        },
        "resolve_embedding": {
            "primary": "local-embedding",
            "fallback": [],
            "capabilities": [],
            "timeout": 5,
        },
        "resolve_llm": {
            "primary": "deepseek-flash",
            "fallback": ["chatgpt"],
            "capabilities": ["json_mode"],
            "timeout": 15,
        },
        "classify_human_review": {
            "primary": "chatgpt",
            "fallback": ["deepseek-pro"],
            "capabilities": ["json_mode"],
            "timeout": 20,
        },
    }
    ```
  - `async def route(task_type: str, context: dict) -> RoutingDecision` — determines which model to use:
    ```python
    @dataclass
    class RoutingDecision:
        task_type: str
        provider: ModelProvider
        model_name: str
        should_fallback: bool
        fallback_chain: list[str]  # remaining fallbacks
        estimated_cost: Decimal
    ```
  - `async def execute(decision: RoutingDecision, prompt: str, schema: type | None = None) -> AIResponse`:
    - Calls the provider's API
    - On success: returns structured response with token counts
    - On transient failure: walks the fallback chain
    - On all fallbacks exhausted: raises `AllProvidersFailedError`
  - Fallback rules (implemented in `should_fallback(result)`):
    - HTTP 5xx → immediately fallback
    - HTTP 429 (rate limited) → wait 5s, retry once, then fallback
    - Timeout → fallback (wait = min(timeout * 0.5, 5s))
    - Invalid JSON response → retry once with stricter prompt, then fallback
    - Empty response → fallback
    - 401/403 (auth error) → do NOT fallback (raise immediately)
  - No model is called during `route()` — only during `execute()`

#### T6: Provider Client Implementations (4h)

**Files:**
- `ai/clients/__init__.py` — NEW
- `ai/clients/openai_compatible.py` — NEW
- `ai/clients/local_llm.py` — NEW

**Acceptance Criteria:**
- `OpenAICompatibleClient`:
  - Supports OpenAI API format and OpenRouter API format
  - Constructor: `__init__(provider: ModelProvider)`
  - Method: `async def chat(prompt, system_prompt, response_model=None, temperature=0.1, max_tokens=None) -> AIResult`
  - Method: `async def chat_structured(prompt, system_prompt, response_model: type[BaseModel]) -> AIResult`
  - Handles auth via `api_key_env` lookup
  - Streams response for cost tracking (counts tokens as they arrive)
- `LocalLLMClient`:
  - For Qwen Local (local endpoint)
  - Same interface as OpenAICompatibleClient
  - Uses `httpx.AsyncClient` with connection pooling
  - No auth required (local network)
- Common `AIResult` dataclass:
  ```python
  @dataclass
  class AIResult:
      content: str
      parsed: BaseModel | None       # if response_model was provided
      model_used: str
      provider_name: str
      input_tokens: int
      output_tokens: int
      total_duration_ms: int
      cost: Decimal
      fallback_chain_used: list[str]  # empty if primary worked
      error: str | None
  ```
- All clients are stateless — one instance per provider, reused across requests

---

### Phase 3: Cost + Observability — Day 3 (12h)

#### T7: Cost Tracker (6h)

**Files:**
- `ai/cost_tracker.py` — NEW
- `ai/models.py` — NEW (shared dataclasses)

**Acceptance Criteria:**
- `CostTracker` class:
  - `async def record(provider_name, model_name, input_tokens, output_tokens, task_type, document_id=None, user_id=None)`
  - `record()` writes to `ai_cost_log` table (see T8)
  - `async def get_cost_by_provider(since: datetime) -> dict[str, Decimal]`
  - `async def get_cost_by_task(since: datetime) -> dict[str, Decimal]`
  - `async def get_daily_cost(date: date) -> Decimal`
  - `async def get_monthly_budget_remaining() -> tuple[Decimal, Decimal]` — (used, budget)
  - `async def would_exceed_budget(estimated_cost: Decimal) -> bool` — check before routing
- Monthly budget from settings: `AI_MONTHLY_BUDGET: Decimal = Decimal("200.00")`
- Cost calculation formula: `(input_tokens / 1000) * cost_per_1k_input + (output_tokens / 1000) * cost_per_1k_output`
- Local models (Qwen) cost: $0 (recorded for accounting, not billed)
- Cost rounding: 6 decimal places
- Thread-safe: uses asyncio lock for concurrent writes

#### T8: Token Accounting + `ai_cost_log` Table (4h)

**Files:**
- `backend/migrations/versions/004_add_ai_cost_log.py` — NEW
- `ai/token_counter.py` — NEW

**Acceptance Criteria:**

**Migration:**
```sql
CREATE TABLE ai_cost_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_name VARCHAR(50) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    total_tokens INTEGER GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,
    cost NUMERIC(12, 6) NOT NULL DEFAULT 0,
    duration_ms INTEGER,
    document_id UUID REFERENCES documents(id),
    user_id UUID REFERENCES users(id),
    success BOOLEAN NOT NULL DEFAULT TRUE,
    error_message TEXT,
    fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ai_cost_log_created ON ai_cost_log(created_at DESC);
CREATE INDEX idx_ai_cost_log_provider ON ai_cost_log(provider_name, created_at);
CREATE INDEX idx_ai_cost_log_task ON ai_cost_log(task_type, created_at);
CREATE INDEX idx_ai_cost_log_document ON ai_cost_log(document_id);
```

**Token Counter:**
- `TokenCounter` class:
  - `async def count_tokens(text: str, model_name: str) -> int`
  - Uses `tiktoken` for OpenAI models (cl100k_base)
  - Uses character-based estimation for local models: `len(text) * 0.25` (Russian text is ~4 chars/token)
  - `count_message_tokens(messages: list[dict])` — counts system + user + assistant turns
  - `count_prompt_tokens(system_prompt, user_prompt)` — returns structured breakdown
- Token counting is approximate (±10%) — exact counts come from API response headers when available

#### T9: Cost Dashboard Data (2h)

**Files:**
- `ai/cost_tracker.py` — continues from T7

**Acceptance Criteria:**
- `CostTracker.get_summary(days=30)` returns:
  ```python
  @dataclass
  class CostSummary:
      total_cost: Decimal
      by_provider: dict[str, Decimal]
      by_task: dict[str, Decimal]
      daily_costs: list[tuple[date, Decimal]]
      total_requests: int
      total_input_tokens: int
      total_output_tokens: int
      avg_cost_per_request: Decimal
      budget_used_pct: float
  ```
- No API endpoint for Sprint 1.5 (data available via Python API for downstream use)
- All methods are read-only queries against `ai_cost_log`

---

### Phase 4: Consolidation — Day 4 (12h)

#### T10: Configuration Update (4h)

**Files:**
- `backend/config.py` — update Settings class
- `.env.example` — update

**Acceptance Criteria:**
- New settings groups added to `Settings`:

```python
# ── AI Embeddings ────────────────────────────────
AI_EMBEDDING_MODEL: str = "intfloat/multilingual-e5-small"
AI_EMBEDDING_BATCH_SIZE: int = 32
AI_EMBEDDING_CACHE_SIZE: int = 1000
AI_EMBEDDING_CACHE_TTL: int = 300  # 5 min

# ── AI Providers ─────────────────────────────────
AI_QWEN_ENDPOINT: str = "http://localhost:8001/v1"
AI_QWEN_TIMEOUT: int = 30
AI_DEEPSEEK_FLASH_BASE: str = "https://openrouter.ai/api/v1"
AI_DEEPSEEK_FLASH_MODEL: str = "deepseek/deepseek-chat"
AI_DEEPSEEK_PRO_BASE: str = "https://openrouter.ai/api/v1"
AI_DEEPSEEK_PRO_MODEL: str = "deepseek/deepseek-reasoner"
AI_GLM_FLASH_BASE: str = "https://openrouter.ai/api/v1"
AI_GLM_FLASH_MODEL: str = "01-ai/yi-1.5-34b-chat"
AI_OPENAI_BASE: str = "https://api.openai.com/v1"
AI_OPENAI_MODEL: str = "gpt-4o"

# ── AI Routing ───────────────────────────────────
AI_DEFAULT_TIMEOUT: int = 30
AI_MAX_RETRIES: int = 2
AI_RATE_LIMIT_RPM: int = 60  # requests per minute global
AI_FALLBACK_ENABLED: bool = True

# ── AI Budget ────────────────────────────────────
AI_MONTHLY_BUDGET: Decimal = Decimal("200.00")
AI_COST_ALERT_THRESHOLD: float = 0.8  # alert at 80% of budget
```

- `from backend.config import settings` still works without circular imports
- All new settings have sensible defaults for development

#### T11: AI Router Integration Test (4h)

**Files:**
- `backend/tests/unit/test_ai_router.py` — NEW
- `backend/tests/unit/test_embedding.py` — NEW
- `backend/tests/unit/test_cost_tracker.py` — NEW

**Acceptance Criteria:**
- `test_ai_router.py`:
  - `test_route_known_task` — routes extract_passport → qwen-local
  - `test_route_fallback_chain` — primary fails → fallback chosen
  - `test_route_unknown_task` — raises `UnknownTaskError`
  - `test_execute_timeout` — timeout triggers fallback
  - `test_execute_rate_limit` — 429 triggers retry + fallback
  - `test_execute_auth_error` — 401 raises immediately
  - `test_routing_table_coverage` — every task type can reach at least one provider
- `test_embedding.py`:
  - `test_embed_single` — returns list of 384 floats
  - `test_embed_batch` — returns correct batch size
  - `test_similarity` — identical vectors → 1.0, orthogonal → 0.0
  - `test_empty_input` → zero vector
  - `test_cache_hit` — second call with same text returns cached
- `test_cost_tracker.py`:
  - `test_record_cost` — inserts and retrieves
  - `test_get_cost_by_provider` — aggregates correctly
  - `test_cost_formula` — verifies calculation
  - `test_budget_remaining` — works with no records
  - `test_concurrent_writes` — no race conditions
- All tests mock external API calls (no real provider calls)
- Mock provider returns controlled responses for timeout, error, success

#### T12: Provider Availability Check + Startup Validation (4h)

**Files:**
- `ai/router.py` — continues from T5
- `backend/main.py` — update lifespan startup

**Acceptance Criteria:**
- `ProviderHealthChecker`:
  - `async def check_provider(provider_name) -> ProviderHealth`
    ```python
    @dataclass
    class ProviderHealth:
        available: bool
        latency_ms: int
        model_loaded: bool       # for local models
        error: str | None
    ```
  - `async def check_all() -> dict[str, ProviderHealth]`
  - For remote providers: lightweight `GET /v1/models` or `HEAD` request
  - For local (Qwen): check if process responds on configured port
- During application startup (lifespan):
  - Run provider health check for all configured providers
  - Log results: `logger.info("AI providers: qwen=UP(12ms), deepseek-flash=UP(340ms), deepseek-pro=DOWN(auth)")`
  - Generate warning for unavailable providers but do NOT block startup
- `ProviderHealth` data available via `AIRouter.get_provider_status()` for downstream dashboards

---

## Dependency Graph

```
T1 (pgvector) ──────────────────────────────────────┐
                                                     │
                                   ┌─────────────────┘
                                   ▼
T2 (embedder) ──► T3 (storage)    T4 (registry) ──► T5 (router) ──► T6 (clients)
                                                     │
                                                     ├──► T7 (cost) ──► T8 (tokens)
                                                     │         │
                                                     │         └──► T9 (summary)
                                                     │
                                                     └──► T12 (health)
                                                           │
T10 (config) ◄─────────────────────────────────────────────┘
                                                     │
T11 (tests) ◄─────────────────────────────────────────┘
```

**Parallelisable groups:**
- T1 + T4 (pgvector + registry — independent)
- T2 + T3 + T6 (embedder, storage, clients — independent after T1/T4)
- T7 + T8 + T9 (cost tracking chain — sequential)
- T10 + T11 + T12 (config, tests, health — depend on T5 but not on each other)

---

## Effort Summary

| Phase | Tasks | Hours | Days | Engineers |
|-------|-------|-------|------|-----------|
| pgvector + Embedding | T1–T3 | 16 | 1 | 2 |
| AI Router | T4–T6 | 16 | 1 | 2 |
| Cost + Observability | T7–T9 | 12 | 1 | 1–2 |
| Consolidation | T10–T12 | 12 | 1 | 2 |
| **Total** | **12 tasks** | **56** | **4** | **2** |

With 2 engineers working full-time: **3.5 calendar days.**

---

## Architecture Diagram (Post-Sprint 1.5)

```
                    ┌──────────────────────┐
                    │   Knowledge Agent    │  ← Sprint 2+
                    │   (pipeline stages)  │
                    └──────────┬───────────┘
                               │ calls
                               ▼
               ┌───────────────────────────────┐
               │         AI Router             │  ← THIS SPRINT
               │                               │
               │  route(task, context) → model │
               │  execute(decision, prompt)    │
               │  fallback: primary → chain    │
               └───────┬───────┬───────┬───────┘
                       │       │       │
              ┌────────┘       │       └────────┐
              ▼                ▼                 ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │Qwen Local    │ │DeepSeek      │ │OpenAI        │
     │(local LLM)   │ │Flash/Pro     │ │GPT-4o        │
     │$0            │ │OpenRouter    │ │Direct API    │
     └──────────────┘ └──────────────┘ └──────────────┘
                                       ┌──────────────┐
                                       │GLM Flash     │
                                       │OpenRouter    │
                                       └──────────────┘

     ┌──────────────────────┐  ┌──────────────────────────┐
     │  Embedding Service   │  │  Cost Tracker             │
     │  multilingual-e5     │  │  ai_cost_log table        │
     │  pgvector HNSW       │  │  monthly budget           │
     │  clients/properties  │  │  provider breakdown       │
     └──────────────────────┘  └──────────────────────────┘
```

---

## Deliverables

### Files Created (13)

| File | Task |
|------|------|
| `ai/__init__.py` | Phase 1 |
| `ai/models.py` | T7 |
| `ai/router.py` | T4, T5, T12 |
| `ai/cost_tracker.py` | T7, T9 |
| `ai/token_counter.py` | T8 |
| `ai/clients/__init__.py` | T6 |
| `ai/clients/openai_compatible.py` | T6 |
| `ai/clients/local_llm.py` | T6 |
| `ai/embeddings/__init__.py` | T1 |
| `ai/embeddings/embedder.py` | T2 |
| `ai/embeddings/storage.py` | T3 |
| `backend/migrations/versions/003_add_pgvector.py` | T1 |
| `backend/migrations/versions/004_add_ai_cost_log.py` | T8 |

### Files Modified (4)

| File | Task |
|------|------|
| `backend/config.py` | T10 |
| `.env.example` | T10 |
| `backend/main.py` | T12 |
| `backend/tests/conftest.py` | T11 (add AI fixtures) |

### Test Files (3)

| File | Task |
|------|------|
| `backend/tests/unit/test_ai_router.py` | T11 |
| `backend/tests/unit/test_embedding.py` | T11 |
| `backend/tests/unit/test_cost_tracker.py` | T11 |

---

## AI Module Structure (Post-Sprint 1.5)

```
ai/
├── __init__.py
├── models.py                  # Shared dataclasses: AIResult, RoutingDecision, etc.
├── router.py                  # ModelRegistry, AIRouter, ProviderHealthChecker
├── cost_tracker.py            # CostTracker
├── token_counter.py           # TokenCounter
│
├── clients/
│   ├── __init__.py
│   ├── openai_compatible.py   # OpenAI + OpenRouter API client
│   └── local_llm.py           # Qwen Local client
│
├── embeddings/
│   ├── __init__.py
│   ├── embedder.py            # EmbeddingService (sentence-transformers)
│   └── storage.py             # EmbeddingStorage (pgvector read/write)
│
├── agents/                    # (future: knowledge agent implementation)
├── extractors/                # (future: entity extraction)
└── prompts/                   # (future: prompt templates)
```

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `sentence-transformers` model download fails | Medium | High | T2: model cached in `~/.cache/huggingface/`. Fallback to zero vectors if model unavailable. |
| pgvector HNSW build time on existing data | Low (no data) | Medium | T1: migration on clean DB. Index build is fast on empty tables. |
| OpenRouter API key not configured | High (dev) | Medium | T12: startup health check warns if keys missing. Providers gracefully degrade. |
| Qwen Local not running | Medium | Low | T12: startup check logs warning. Router treats as unavailable. Fallback to DeepSeek. |
| Token counting inaccurate for Russian text | Medium | Low | T8: uses approximate char-based method. Exact counts from API when available. |
| Concurrent cost log writes | Low | Low | T7: asyncio lock. Append-only table, no contention. |

---

## Integration Points

### Downstream Dependencies (Sprint 2+)

| Downstream System | Uses |
|-------------------|------|
| Knowledge Agent pipeline | `AIRouter.route()` + `.execute()` for classification, extraction |
| Entity Resolution | `EmbeddingService.embed()` + `EmbeddingStorage.search_similar()` for fuzzy matching |
| Lead Scoring | `AIRouter` for LLM-based enrichment |
| Document Classification | `AIRouter` for Stage 3 LLM classification |
| Cost Dashboard | `CostTracker.get_summary()` for admin UI |

### Upstream Dependencies (Sprint 1)

| Sprint 1 Artifact | Used By |
|-------------------|---------|
| `backend/database.py` | EmbeddingStorage, ai_cost_log writes |
| `backend/config.py` | All AI settings |
| `backend/exceptions.py` | AI exception hierarchy |
| `backend/logging_.py` | AI logging |
| `backend/migrations/` | pgvector + cost log migrations |

---

## Verification

After Sprint 1.5, the following should work:

```python
# Embedding
from ai.embeddings.embedder import embedder
vec = await embedder.embed("Иванов Иван Иванович")
assert len(vec) == 384

# AI Router
from ai.router import router
decision = await router.route("extract_passport")
result = await router.execute(decision, "Паспорт: 4516 123456")
assert result.model_used == "qwen-local"  # or fallback
assert result.input_tokens > 0

# Cost Tracking
from ai.cost_tracker import tracker
await tracker.record("openrouter", "deepseek-flash", 150, 45, "classify_llm")
summary = await tracker.get_summary(days=30)
assert summary.total_cost > 0

# pgvector
# psql: SELECT * FROM pg_extension WHERE extname = 'vector';
# psql: \d clients  →  embedding vector(384)
```
