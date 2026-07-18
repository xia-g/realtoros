|# ADR-0013 Review|

**Date:** 2026-06-07
**Reviewer:** Principal Architect
**Subject:** ADR-0013 Lead Management Model (Proposed)

---

## Review Summary

| Dimension | Rating | Verdict |
|-----------|--------|---------|
| Problem identification | ⭐⭐⭐⭐⭐ | Correctly identifies 5 limitations of current model |
| Solution approach | ⭐⭐⭐⭐ | Option C (separate entity) is the right call |
| Entity design | ⭐⭐⭐ | Good coverage, but 2 structural issues (see A, B) |
| Impact analysis | ⭐⭐⭐⭐ | Comprehensive, 7 frozen files listed |
| Risk assessment | ⭐⭐⭐ | Missing scoring architecture risk (see C) |
| Knowledge Graph fit | ⭐⭐⭐ | Edge types correct, node type missing (see KG) |

**Overall: Accepted with Required Changes**

---

## 1. Lead Lifecycle

### Accepted

The status progression `new → contact_made → qualifying → qualified → converted | lost | spam` correctly models the real estate lead funnel. The separation from `Client.status` is the core improvement — leads and clients have fundamentally different lifecycles.

### Required Change: Add `lead_events` Table

The proposal defines 7 statuses with transitions but provides no audit trail. Every status change is a business event that must be recorded.

```sql
CREATE TABLE lead_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    event_type VARCHAR(30) NOT NULL,
    -- status_changed | assigned | scored | qualified | converted | note_added

    from_status lead_status,         -- NULL for creation
    to_status lead_status,           -- NULL for non-status events

    from_priority VARCHAR(10),       -- for priority changes
    to_priority VARCHAR(10),

    from_score FLOAT,                -- for score changes
    to_score FLOAT,

    from_user_id UUID REFERENCES users(id),   -- previous assignee
    to_user_id UUID REFERENCES users(id),     -- new assignee

    change_reason TEXT,               -- why the change happened
    changed_by UUID NOT NULL REFERENCES users(id),
    -- NULL for system events (auto-scoring, auto-assignment)

    metadata JSONB,                   -- additional context

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_lead_events_lead ON lead_events(lead_id);
CREATE INDEX idx_lead_events_type ON lead_events(event_type);
CREATE INDEX idx_lead_events_created ON lead_events(created_at DESC);
```

**Rationale:**
- Without `lead_events`, you cannot calculate `time_in_status` — the most basic lead analytics metric
- ML scoring models require status transition history as training data
- Agent performance auditing requires knowing who did what and when
- GDPR compliance requires proving exactly when and why a lead was marked as `lost` or `spam`

### Optional Improvement: Status Transition Rules

Document which transitions are valid and which should be automatically detected:

```
new → contact_made          ← auto on first outbound communication
contact_made → qualifying   ← manual (agent determines needs info)
qualifying → qualified      ← manual (budget + property type + timeline known)
qualified → converted       ← auto on Client record creation
qualified → lost            ← manual
any → spam                  ← manual (hard override)
```

---

## 2. Lead → Client Conversion

### Accepted

The conversion mechanism (set `leads.client_id` when a Client record exists or is created) is correct. The deal path (lead can have `deal_id` directly) handles the case where a lead results in a deal without a formal Client relationship (e.g., one-time transaction).

### Required Change: Remove `clients.lead_id`

The proposal adds **both** `leads.client_id` (FK → clients) and `clients.lead_id` (FK → leads). This creates a bidirectional FK pair that is a structural design flaw.

```
┌────────────────┐         ┌────────────────┐
│    leads       │         │    clients     │
├────────────────┤         ├────────────────┤
│ id UUID (PK)  │         │ id UUID (PK)   │
│ client_id FK──┼────────►│                │
└────────────────┘         │ lead_id FK─────┼──? (redundant)
                           └────────────────┘
```

**Problems with bidirectional FK:**

1. **Circular dependency on INSERT:** If Lead creates Client, you must INSERT Lead first (with `client_id = NULL`), then INSERT Client, then UPDATE Lead to set `client_id`. If Client creates Lead, the reverse. Either way, one of the FKs must be nullable and one UPDATE is always required.

2. **Inconsistency risk:** Nothing prevents `leads.client_id = X` while `clients.lead_id = Y` where `X ≠ Y`. Two FKs can contradict each other with no resolution rule.

3. **INSERT ordering problem:** With strict FK validation, you can never INSERT with both FKs set simultaneously in a single statement because the referenced record doesn't exist yet.

4. **No semantic owner:** Which table is the "source of truth" for the relationship? Both claim ownership.

**Resolution:** Remove `clients.lead_id`. Keep only `leads.client_id`.

- The **Lead** is the source entity. The **Client** is the result. The Lead knows which Client it produced.
- To find which Lead produced a Client: `SELECT * FROM leads WHERE client_id = :client_id`
- This query is indexed by `idx_leads_client` (already proposed).

### Optional Improvement: Conversion Transaction

Define the conversion as an atomic transaction:

```sql
BEGIN;
    -- 1. Create or link client
    INSERT INTO clients (...) VALUES (...)
    RETURNING id INTO client_id;

    -- 2. Update lead
    UPDATE leads
    SET status = 'converted',
        client_id = client_id,
        converted_at = NOW()
    WHERE id = lead_id;

    -- 3. Record event
    INSERT INTO lead_events (lead_id, event_type,
        from_status, to_status, changed_by)
    VALUES (lead_id, 'converted',
        'qualified', 'converted', user_id);

    -- 4. Create graph edge (per ADR-0008)
    INSERT INTO graph_edges (source_node_id, target_node_id,
        edge_type, source)
    VALUES (
        (SELECT id FROM graph_nodes WHERE entity_id = lead_id AND entity_table = 'leads'),
        (SELECT id FROM graph_nodes WHERE entity_id = client_id AND entity_table = 'clients'),
        'converts_to', 'conversion'
    );
COMMIT;
```

---

## 3. Multi-Lead Support

### Accepted

The data model correctly supports multiple leads for the same person:
- Same phone number → separate leads from different sources (Telegram + Avito)
- Each lead has its own `source`, `source_id`, `source_metadata`
- When one lead converts to Client, other leads for the same person remain independently trackable

### Required Change: Clarify `source_id` Semantics

The proposal uses `source_id: VARCHAR` with source-specific meanings. This needs per-source documentation:

| Source | `source_id` Semantics | Uniqueness | Notes |
|--------|----------------------|------------|-------|
| telegram | `chat_id` | Unique within source | A chat can produce multiple leads over time. Consider appending `_message_id` for one-lead-per-message granularity. |
| avito | `listing_id` | Unique | One lead per listing. Multiple leads for same listing → update existing lead. |
| cian | `property_id` | Unique | Same as Avito. |
| referral | `referring_client_id` | Non-unique | Same referrer can send multiple leads. Composite: (referring_client_id, created_at). |
| site | `form_submission_id` | Unique | One submission = one lead. |
| call | `call_log_id` | Unique | One call recording = one lead. |

**Recommendation:** Add a `source_id_description` column or document in `lead.md` what each source's `source_id` means. The current ambiguity will cause integration bugs.

### Optional Improvement: Lead Merge

When two leads from different sources are identified as the same person (e.g., same phone), provide a merge mechanism:

```python
LEAD_MERGE_RULES = {
    "strategy": "keep_earliest_lead, append_source",
    "priority": ["client_match", "phone_match", "name_fuzzy"],
    "fields": {
        "budget_min": "max",           # take the highest
        "budget_max": "max",
        "locations": "union",
        "notes": "concat",
        "source": "keep_primary",       # first source is primary
        "source_metadata": "merge_jsonb",  # merge all sources
    },
    "events": ["lead_merged"],
}
```

---

## 4. Analytics Requirements

### Accepted

The proposed indexes support basic analytics queries:
- `idx_leads_source_status` — source performance analysis
- `idx_leads_created` — lead volume over time
- `idx_leads_assigned` — agent workload

### Required Change: Add `lead_events` for Time-Based Analytics

Without `lead_events`, the following essential analytics queries are impossible:

```sql
-- Lead conversion time (impossible without event timestamps)
SELECT AVG(le.converted_at - le.created_at) AS avg_conversion_time
FROM leads l
JOIN lead_events le ON le.lead_id = l.id
WHERE le.event_type = 'converted';

-- Pipeline bottleneck detection
SELECT to_status, AVG(time_in_status) AS avg_days
FROM lead_events
WHERE to_status IN ('new', 'contact_made', 'qualifying', 'qualified')
GROUP BY to_status;

-- Agent response time (time from lead creation to first_outbound)
SELECT l.assigned_to,
       AVG(le.created_at - l.created_at) AS avg_response_time
FROM leads l
JOIN lead_events le ON le.lead_id = l.id
WHERE le.event_type = 'status_changed'
  AND le.to_status = 'contact_made'
GROUP BY l.assigned_to;

-- Source conversion rate
SELECT l.source,
       COUNT(*) AS total_leads,
       COUNT(*) FILTER (WHERE l.status = 'converted') AS converted,
       COUNT(*) FILTER (WHERE l.status = 'lost') AS lost,
       COUNT(*) FILTER (WHERE l.status = 'spam') AS spam
FROM leads l
GROUP BY l.source;
```

### Additional Indexes for Analytics

```sql
-- Lead volume by date range (for reporting)
CREATE INDEX idx_leads_source_created ON leads(source, created_at);

-- Agent performance
CREATE INDEX idx_leads_assigned_created ON leads(assigned_to, created_at);
CREATE INDEX idx_lead_events_changed_by ON lead_events(changed_by);
```

---

## 5. Knowledge Graph Integration

### Accepted

The edge types `converts_to` and `assigned_to_agent` are correct.

### Required Change: Add `lead` to `graph_nodes.node_type`

The proposal mentions this in the consistency check but it must be formally added to the ADR's impact section:

```sql
ALTER TYPE node_type ADD VALUE 'lead';
ALTER TYPE edge_type ADD VALUE 'converts_to';
ALTER TYPE edge_type ADD VALUE 'assigned_to_agent';
ALTER TYPE edge_type ADD VALUE 'qualified_by_agent';
ALTER TYPE edge_type ADD VALUE 'generated_deal';
ALTER TYPE edge_type ADD VALUE 'from_communication';  -- lead → communication
```

### Knowledge Graph Query Patterns for Leads

```sql
-- Find all leads that converted to a deal
SELECT l.id, l.source, l.score, d.id AS deal_id, d.price
FROM leads l
JOIN deals d ON d.id = l.deal_id
WHERE l.status = 'converted'
  AND l.deal_id IS NOT NULL;

-- Agent lead pipeline (who is working what)
SELECT u.full_name AS agent,
       l.status,
       COUNT(*) AS lead_count
FROM leads l
JOIN users u ON u.id = l.assigned_to
GROUP BY u.full_name, l.status;

-- Lead-to-client-to-deal chain (path query via graph)
SELECT n1.label AS lead_name,
       e1.edge_type AS step1,
       n2.label AS client_name,
       e2.edge_type AS step2,
       n3.label AS deal_ref
FROM graph_edges e1
JOIN graph_nodes n1 ON n1.id = e1.source_node_id
JOIN graph_nodes n2 ON n2.id = e1.target_node_id
LEFT JOIN graph_edges e2 ON e2.source_node_id = n2.id
LEFT JOIN graph_nodes n3 ON n3.id = e2.target_node_id
WHERE n1.node_type = 'lead'
  AND e1.edge_type = 'converts_to';
```

---

## 6. Future AI Scoring

### Required Change: Define Scoring Architecture

The proposal has `score: FLOAT DEFAULT 0.0` with a vague note about computation. This is insufficient. Lead scoring is a non-trivial subsystem that must be defined at the architectural level.

**Minimum fields for scoring:**

```diff
+ score_components JSONB   ← breakdown of score by factor
  {
    "source_reliability": 0.15,
    "budget_alignment": 0.20,
    "response_rate": 0.10,
    "urgency_signal": 0.25,
    "property_match": 0.15,
    "location_match": 0.15
  }

+ score_version VARCHAR(20)  ← which scoring model produced this
  "v1-rule-based" | "v2-ml-random-forest" | "v3-ml-xgboost"

+ last_scored_at TIMESTAMPTZ ← when was score last computed

+ last_auto_assigned_at TIMESTAMPTZ  ↑ avoid re-assigning hot leads
```

**Scoring engine architecture:**

```
Lead Created / Updated
    │
    ▼
┌──────────────────────────────────────────┐
│ Scoring Engine                            │
│                                          │
│ 1. Rule-based (immediate, < 10ms)        │
│    - Source reputation: telegram=0.8,    │
│      avito=0.6, referral=0.9            │
│    - Budget exists: +0.2                │
│    - Phone provided: +0.1               │
│    - Has specific property type: +0.15  │
│                                          │
│ 2. ML-based (async, batch)               │
│    - Feature set: source, budget,        │
│      property_type, response_time,       │
│      historical conversion rate from     │
│      similar leads                       │
│    - Model: Random Forest classifier     │
│    - Retrained: weekly                  │
│                                          │
│ 3. Combined score: rule * 0.4 + ml * 0.6│
│    Stored in lead.score                 │
│    + components in lead.score_components │
└──────────────────────────────────────────┘
    │
    ▼
Priority Assignment
├── score ≥ 0.80 → hot
├── score ≥ 0.60 → warm
├── score ≥ 0.30 → cold
└── score < 0.30 → parked
    │
    ▼
Auto-Assignment (if score ≥ 0.80 and unassigned)
├── Round-robin to available agents
├── Respects agent lead limit (max 50 active)
└── Logged to lead_events
```

**Event logging for scoring:**

Every score recalculation must be logged:

```sql
INSERT INTO lead_events (lead_id, event_type,
    from_score, to_score, change_reason, changed_by)
VALUES (:lead_id, 'scored',
    0.0, 0.75, 'rule_based_scoring_v1', NULL);
```

### Optional Improvement: Scoring Data Pipeline

```python
SCORING_DATA_SOURCES = {
    "lead_properties": {
        "source", "budget_max", "property_type",
        "has_phone", "has_email", "locations",
    },
    "behavioral": {
        "response_time",          # first_response_at - created_at
        "communication_count",    # COUNT(communications)
        "document_count",         # COUNT(documents)
    },
    "historical": {
        "source_conversion_rate", # by source
        "agent_performance",      # by assigned_to
    },
    "external": {
        "market_conditions",      # future: interest rates, supply
        "seasonality",            # month of year
    },
}
```

---

## 7. Future Telegram Integration

### Accepted

The Telegram lead source is well-specified with `source_metadata` containing `username`, `chat_type`, `message_text`, and `message_date`.

### Required Change: Clarify Telegram lead creation triggers

The proposal says "Telegram handler: auto-create Lead instead of Client for first contact". This needs more detail:

```python
TELEGRAM_LEAD_CREATION = {
    "trigger": "first direct message from unknown user",
    "resolution": {
        "1": "Check if phone number exists in leads OR clients",
        "2": "Match existing → link new lead to existing client",
        "3": "No match → create new lead with source=telegram",
    },
    "source_id": "chat_id",
    "source_metadata": {
        "username": "str",
        "first_name": "str",
        "last_name": "str",
        "language_code": "str",
        "chat_type": "private | group | supergroup",
        "message_text": "str (first message only)",
        "message_date": "timestamp",
    },
    "auto_fields": {
        "priority": "warm",         # Telegram leads default warm
        "score": 0.5,               # neutral starting score
        "interest_type": "unknown",
    },
}
```

### Optional: Telegram-specific lead enrichment

After creation, the Knowledge Agent should enrich Telegram leads:

1. Extract phone from message text → `phone` field
2. Extract budget/location from message → `budget_min`, `locations`
3. Set `interest_type` based on message content (LLM: Qwen Local)
4. Create initial Communication record linking lead to message
5. Create initial Task for agent: "Review new lead from Telegram"

```python
TELEGRAM_ENRICHMENT = {
    "immediate": {
        "phone_extraction": "regex in message_text",
        "create_communication": "link lead → telegram message",
    },
    "async": {
        "llm_extraction": "Qwen Local: extract budget, location, interest",
        "auto_task": "if score ≥ 0.60: create task 'Contact new lead'",
    },
}
```

---

## Specific Evaluations

### A. `clients.lead_id` vs `leads.client_id`

**Verdict: Keep ONLY `leads.client_id`. Remove `clients.lead_id`.**

| Criterion | `leads.client_id` | `clients.lead_id` | Both |
|-----------|-------------------|-------------------|------|
| Direction | Lead → Client (forward) | Client → Lead (reverse) | bidirectional |
| INSERT order | Lead first, Client second, UPDATE Lead | Client first, Lead second, UPDATE Client | always requires UPDATE |
| Consistency risk | None (single FK) | None (single FK) | Can contradict |
| Query pattern | `SELECT * FROM leads WHERE client_id = :id` | `SELECT * FROM clients WHERE lead_id = :id` | Slower (two queries) |
| Semantic | "This lead produced this client" | "This client came from this lead" | Both say same thing |

**Decision rationale:** The lead is the source of the relationship. The client is the outcome. The FK should point from source to outcome, not the reverse. The reverse query (`which lead produced client X?`) is a simple indexed lookup — it doesn't need a FK.

### B. Need for `lead_events` Table

**Verdict: Required. Add `lead_events` before acceptance.**

Without it, essential analytics, audit, and ML capabilities are impossible:
- Status transition timing
- Agent response time
- Pipeline bottleneck analysis
- ML training data generation
- GDPR compliance (lead disposition proof)

The table is lightweight (5 columns + 3 timestamps + 2 FKs) and adds no operational complexity. It is an INSERT-only table with no UPDATE or DELETE — the fastest possible write pattern.

### C. Need for Lead Scoring Architecture

**Verdict: Required. Define scoring fields before acceptance. Full scoring engine can be deferred to implementation.**

The minimum viable scoring fields are:
- `score_components JSONB` — factor breakdown
- `score_version VARCHAR` — model tracking
- `last_scored_at TIMESTAMPTZ` — staleness detection

Without these, the `score` field is a black box:
- You cannot audit why a score is 0.7 vs 0.3
- You cannot detect stale scores (lead behaviour changed but score didn't)
- You cannot A/B test scoring models
- You cannot debug scoring bugs

The scoring ENGINE can be implemented later (rule-based → ML), but the data model must support it from the start.

### D. Future Multi-Source Ingestion

**Verdict: Accepted with clarification.**

The design scales well:
- New source → `ALTER TYPE lead_source ADD VALUE` + new `source_metadata` schema
- `source_metadata JSONB` handles any payload without schema changes
- Composite index `(source, source_id)` handles cross-source uniqueness

**Required clarification:** Document `source_id` semantics per source (see Section 3).

**Long-term scalability consideration:** At 100K+ leads/month, `source_metadata JSONB` on every `SELECT` will slow down queries. Future optimization: move `source_metadata` to a separate `lead_source_data` table and keep the hot columns (score, status, priority) on `leads`. Not required for V1.

---

## Required Changes (Blocking Acceptance)

| # | Change | Priority | Effort | Justification |
|---|--------|----------|--------|---------------|
| 1 | **Remove `clients.lead_id`** | Critical | 1 line | Bidirectional FK is a structural design flaw |
| 2 | **Add `lead_events` table DDL** | Critical | 20 lines | Essential for analytics, audit, and ML |
| 3 | **Add `score_components`, `score_version`, `last_scored_at` to Lead** | High | 3 columns | Scoring must be auditable from day one |
| 4 | **Document `source_id` semantics per source** | High | 10 lines | Prevents integration bugs |
| 5 | **Add Knowledge Graph node/edge types to impact section** | Medium | 5 lines | Incomplete KG integration scope |
| 6 | **Define Telegram lead creation triggers in detail** | Medium | 15 lines | Prevents Telegram handler ambiguity |

## Required Changes Summary

1. `.lead_id` → REMOVE: `clients.lead_id` 
   `leads.client_id` → KEEP as single FK

2. `+ lead_events` → ADD: table with event_type, 
   from_status/to_status, score tracking, changed_by

3. `+ score fields` → ADD: score_components JSONB, 
   score_version VARCHAR, last_scored_at TIMESTAMPTZ

4. `+ source docs` → ADD: per-source source_id 
   semantics table

5. `+ KG scope` → ADD: node_type 'lead', edge_type 
   values to Impact section

6. `+ Telegram detail` → ADD: trigger, resolution, 
   enrichment specification

## Optional Improvements

| # | Improvement | Value | Effort |
|---|-------------|-------|--------|
| 1 | Lead merge mechanism (same person, different sources) | Medium | Complex |
| 2 | Scoring engine architecture (rule-based → ML) | High | Complex |
| 3 | `source_metadata` hot/cold split at scale | Low | Future |
| 4 | Status transition rules documentation | Medium | Simple |

## Verdict

**Status: Returned for Revisions**

The proposal is structurally sound and the separate-entity approach (Option C) is the correct decision. The three structural issues (bidirectional FK, missing events table, incomplete scoring fields) must be resolved before acceptance. Estimated revision effort: 1 hour.

Once revised, the ADR can be Accepted and the implementation can proceed as specified in ADR-0012's change procedure.
