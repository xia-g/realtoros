|# ADR-0013 Revision 2|

Date: 2026-06-07|

## Status

Revised — supercedes ADR-0013 v1 (Proposed).

## Context

The current domain model uses `Client.status = 'lead'` to represent unqualified leads. This collapses two distinct concepts — potential business (leads) and verified relationships (clients) — into one table. Five specific limitations were identified in ADR-0013 v1:

1. Source-specific metadata cannot be stored or queried
2. Lead and Client lifecycles are conflated
3. Multi-source attribution (Avito → Referral → Telegram) is impossible
4. Qualification tracking has no mechanism
5. Lead scoring has no data model

ADR-0013 v1 proposed a separate `Lead` entity (Option C). Technical review (ADR-0013 Review) confirmed Option C is correct but identified 6 required changes:

| # | Change | Source |
|---|--------|--------|
| 1 | Remove `clients.lead_id` bidirectional FK | Review §2 |
| 2 | Add `lead_events` audit table | Review §1, §4 |
| 3 | Add scoring fields (components, version, last_scored_at) | Review §6 |
| 4 | Document source_id semantics per source | Review §3 |
| 5 | Define Telegram lead lifecycle | Review §7 |
| 6 | Add Knowledge Graph node/edge types | Review §5 |

This revision incorporates all 6 changes and additionally defines the complete Lead Lifecycle Model.

---

## Complete Lead Lifecycle Model

### State Machine

```
                    ┌─────────┐
                    │   new   │ ← Lead created (any source)
                    └────┬────┘
                         │
                    auto │ first outbound communication
                         ▼
                    ┌────────────┐
                    │contact_made│ ← Agent reached out
                    └─────┬──────┘
                          │
                    auto/ │ agent gathered initial info
                    manual │
                          ▼
                    ┌────────────┐
                    │ qualifying │ ← Needs info gathering
                    └─────┬──────┘
                          │
                    auto/ │ budget + property type + timeline known
                    manual │
                          ▼
                    ┌──────────┐
                    │ qualified│ ← Ready to convert
                    └────┬─────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
              ▼          ▼          ▼
        ┌──────────┐ ┌──────┐ ┌──────┐
        │converted │ │ lost │ │spam  │
        └──────────┘ └──────┘ └──────┘
              │
              ▼
        ┌──────────┐
        │  Client  │
        └──────────┘
```

### Full Transition Matrix

| From | To | Trigger | Authority | Auto Conditions |
|------|----|---------|-----------|-----------------|
| **new** | contact_made | First outbound communication | System | Auto-detect when first `Communication` created with direction='outgoing' |
| **new** | spam | Agent flags as spam | Agent | Manual override. Hard delete from active pipeline. |
| **new** | lost | Agent marks not interested | Agent | Manual. Requires reason. |
| **contact_made** | qualifying | Agent begins info gathering | Agent | Manual. Creates `lead_events` with change_reason. |
| **contact_made** | new | Agent resets lead | Agent | Rare — when initial contact was premature. |
| **contact_made** | spam | Agent flags as spam | Agent | Requires evidence (wrong number, auto-reply bot). |
| **contact_made** | lost | Agent gives up | Agent | After 3+ failed contact attempts. |
| **qualifying** | qualified | Budget + property type + timeline known | Agent | Minimum 3 criteria met. Can be auto-detected if all fields populated. |
| **qualifying** | contact_made | Needs more initial info | Agent | Rollback when qualification stalled. |
| **qualifying** | lost | Cannot qualify | Agent | No budget, no interest, no timeline. |
| **qualifying** | spam | Evidently spam | Agent | E.g., competitor intelligence gathering. |
| **qualified** | converted | Client record created or linked | System | Auto. Atomic transaction (see Conversion Transaction §3). |
| **qualified** | lost | Lead expired | Agent/System | Auto after 30 days without conversion. Configurable. |
| **qualified** | qualifying | Not enough info after all | Agent | Rollback. Agent must record what's missing. |
| **lost** | qualifying | Lead re-engages | Agent | Reopening flow (see §6). |
| **lost** | new | Complete reset | Agent | Rare. Clears all qualification data. |
| **spam** | — | Terminal state | — | No outgoing transitions. Admin-only deletion. |

### Invalid Transitions (explicitly forbidden)

| From | To | Reason |
|------|----|--------|
| converted | any | Client exists. Lead is historical. Create new Lead if re-engagement. |
| spam | any | Spam is terminal. Admin-only hard delete if mis-flagged. |
| lost | converted | Cannot convert a lost lead. Must reopen → qualify → convert. |

---

## 1. Revised Lead Entity

### Entity Definition

```sql
CREATE TYPE lead_source AS ENUM (
    'telegram', 'avito', 'cian', 'referral', 'site', 'call', 'manual'
);

CREATE TYPE lead_status AS ENUM (
    'new', 'contact_made', 'qualifying', 'qualified',
    'converted', 'lost', 'spam'
);

CREATE TYPE interest_type AS ENUM (
    'buy', 'rent_short', 'rent_long', 'sell',
    'commercial_buy', 'commercial_rent', 'unknown'
);

CREATE TABLE leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source (where this lead came from)
    source lead_source NOT NULL,
    source_id VARCHAR(255),             -- external ID, semantics per §2
    source_metadata JSONB DEFAULT '{}', -- raw source payload

    -- Identity (core fields, gradually filled)
    full_name VARCHAR(255),
    phone VARCHAR(20),
    email VARCHAR(255),
    telegram_id VARCHAR(100),
    telegram_username VARCHAR(100),

    -- Interest (what they're looking for)
    interest_type interest_type NOT NULL DEFAULT 'unknown',
    property_type VARCHAR(20),           -- apartment|house|commercial|land|...
    budget_min NUMERIC(15,2),
    budget_max NUMERIC(15,2),
    locations TEXT[] DEFAULT '{}',

    -- Status & lifecycle
    status lead_status NOT NULL DEFAULT 'new',
    previous_status lead_status,         -- for reversion tracking
    status_changed_at TIMESTAMPTZ,

    -- Scoring (see §8)
    score FLOAT DEFAULT 0.0,
    score_components JSONB DEFAULT '{}', -- factor breakdown
    score_version VARCHAR(20),           -- "v1-rule-based" | "v2-ml-..."
    last_scored_at TIMESTAMPTZ,

    -- Timing & priority
    priority VARCHAR(10) DEFAULT 'cold', -- hot|warm|cold|parked
    first_response_at TIMESTAMPTZ,       -- time from creation to first agent action
    last_contact_at TIMESTAMPTZ,

    -- Assignment & qualification
    assigned_to UUID REFERENCES users(id),
    assigned_at TIMESTAMPTZ,
    last_auto_assigned_at TIMESTAMPTZ,   -- avoid re-assigning hot leads
    qualified_by UUID REFERENCES users(id),
    qualified_at TIMESTAMPTZ,
    qualification_note TEXT,

    -- Conversion (Lead → Client → Deal)
    -- Single FK: lead → client. NO reverse FK on clients table.
    client_id UUID REFERENCES clients(id),  -- set when converted
    converted_at TIMESTAMPTZ,
    deal_id UUID REFERENCES deals(id),      -- direct link if lead → deal without client

    -- Notes & audit
    tags TEXT[] DEFAULT '{}',
    notes TEXT,
    created_by UUID NOT NULL REFERENCES users(id),

    -- Soft delete (per ADR-0010)
    deleted_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Key Design Decision: Single FK Direction

**`leads.client_id` EXISTS. `clients.lead_id` DOES NOT EXIST.**

```
leads                         clients
┌──────────────────┐          ┌──────────────────┐
│ id UUID (PK)     │          │ id UUID (PK)     │
│ client_id FK─────┼─────────►│                  │
└──────────────────┘          └──────────────────┘
```

Rationale:
- Lead is the source. Client is the outcome. FK points source → outcome.
- To find which Lead produced a Client: `SELECT * FROM leads WHERE client_id = :id`
- Index `idx_leads_client` on `leads.client_id` makes this a fast unique lookup.
- No circular dependency, no INSERT ordering problem, no inconsistency risk.

### Client Entity Changes

```diff
  type: buyer|seller|tenant|landlord|investor|partner
- status: lead|active|inactive|archived|blacklisted
+ status: active|inactive|archived|blacklisted
+ source: referral|site|telegram|call|other|lead_conversion
- NO lead_id column added to clients table
```

### Indexes

```sql
-- Core lookups
CREATE INDEX idx_leads_source_status ON leads(source, status);
CREATE INDEX idx_leads_client ON leads(client_id) WHERE client_id IS NOT NULL;
CREATE INDEX idx_leads_assigned ON leads(assigned_to) WHERE assigned_to IS NOT NULL;
CREATE INDEX idx_leads_score ON leads(score DESC) WHERE status NOT IN ('converted', 'lost', 'spam');
CREATE INDEX idx_leads_priority ON leads(priority) WHERE status NOT IN ('converted', 'lost', 'spam');
CREATE INDEX idx_leads_created ON leads(created_at DESC);
CREATE INDEX idx_leads_source_id ON leads(source, source_id);
CREATE INDEX idx_leads_source_created ON leads(source, created_at);
CREATE INDEX idx_leads_assigned_created ON leads(assigned_to, created_at);
CREATE INDEX idx_leads_phone ON leads(phone) WHERE phone IS NOT NULL;
CREATE INDEX idx_leads_telegram ON leads(telegram_id) WHERE telegram_id IS NOT NULL;
```

---

## 2. Source ID Semantics

Each source uses `source_id` differently. The following table documents the exact semantics:

| Source | `source_id` Value | Uniqueness Constraint | Description | Example |
|--------|-------------------|-----------------------|-------------|---------|
| **telegram** | `chat_id` + `_message_id` | Unique per (chat, message) | Telegram chat ID and first message ID. `chat_id` alone is NOT unique — a group chat can produce multiple leads over time. Append `_{message_id}` for one-lead-per-message granularity. | `-1001234567890_5432` |
| **avito** | `listing_id` | Unique per listing | Avito ad/listing ID. Multiple leads for the same listing update the existing lead (re-engagement), not create a new one. | `1234567890` |
| **cian** | `property_id` | Unique per property | CIAN property ID. Same dedup rule as Avito: same property → update existing lead. | `987654321` |
| **referral** | `referring_client_id` | Non-unique | The UUID of the Client who made the referral. Same referrer can send multiple leads — composite uniqueness with `created_at` or use `id` as tiebreaker. | `550e8400-e29b-...` |
| **site** | `form_submission_id` | Unique | Web form submission tracking ID. One interaction = one lead. | `sub_abc123` |
| **call** | `call_log_id` | Unique | Call log entry UUID. Each inbound call can produce one lead. | `call_20260607_001` |
| **manual** | `employee_id` | Non-unique | UUID of the agent who manually created the lead. Agent can create many leads. | `7a1f2c3d-...` |

### Dedup Rules by Source

```python
SOURCE_DEDUP = {
    "telegram": {
        "key": "source_id",          # (chat_id + message_id) is unique
        "action": "create_new",      # every message is a new lead opportunity
    },
    "avito": {
        "key": "source_id",          # listing_id
        "action": "update_existing", # same listing → update budget/interest, reset status to 'new'
    },
    "cian": {
        "key": "source_id",          # property_id
        "action": "update_existing", # same as Avito
    },
    "referral": {
        "key": "phone + full_name",  # no unique source_id
        "action": "match_by_identity",
    },
    "site": {
        "key": "source_id",          # form_submission_id
        "action": "create_new",
    },
    "call": {
        "key": "source_id",          # call_log_id
        "action": "create_new",
    },
    "manual": {
        "key": "phone",              # avoid duplicate manual entries
        "action": "match_by_phone",
    },
}
```

---

## 3. Lead → Client Conversion

### Conversion Rules

A lead may be converted to a Client when ALL of the following are true:

| Rule | Condition | Enforcement |
|------|-----------|-------------|
| Status | `status = 'qualified'` | System prevents conversion from any other status |
| Identity | `full_name` is not NULL | Required for Client record |
| Contact | At least one of: `phone`, `email`, `telegram_id` | Client must be reachable |
| Interest | At least one of: `interest_type ≠ unknown`, `budget_max > 0` | Client must have a purpose |

### Atomic Conversion Transaction

```sql
BEGIN;

    -- 1. Create client from lead data
    INSERT INTO clients (
        full_name, phone, email, telegram_id,
        telegram_username, type, status, source,
        notes, tags, created_by
    ) VALUES (
        lead.full_name, lead.phone, lead.email,
        lead.telegram_id, lead.telegram_username,
        CASE lead.interest_type
            WHEN 'buy' THEN 'buyer'
            WHEN 'sell' THEN 'seller'
            WHEN 'rent_short' THEN 'tenant'
            WHEN 'rent_long' THEN 'tenant'
            ELSE 'buyer'
        END,
        'active',
        CASE lead.source
            WHEN 'telegram' THEN 'telegram'
            WHEN 'referral' THEN 'referral'
            ELSE 'lead_conversion'
        END,
        CONCAT('Converted from lead: ', lead.id::text, E'\n', lead.notes),
        lead.tags,
        COALESCE(lead.assigned_to, lead.created_by)
    )
    RETURNING id INTO client_id;

    -- 2. Update lead with conversion data
    UPDATE leads
    SET status = 'converted',
        client_id = client_id,
        converted_at = NOW(),
        previous_status = 'qualified',
        status_changed_at = NOW()
    WHERE id = lead_id;

    -- 3. Record event
    INSERT INTO lead_events (lead_id, event_type,
        from_status, to_status, changed_by)
    VALUES (lead_id, 'converted',
        'qualified', 'converted', lead.assigned_to);

    -- 4. Create graph edge
    INSERT INTO graph_edges (
        source_node_id, target_node_id,
        edge_type, source, created_at
    )
    SELECT
        gn_lead.id, gn_client.id,
        'converts_to', 'conversion', NOW()
    FROM graph_nodes gn_lead, graph_nodes gn_client
    WHERE gn_lead.entity_table = 'leads'
      AND gn_lead.entity_id = lead_id
      AND gn_client.entity_table = 'clients'
      AND gn_client.entity_id = client_id;

    -- 5. Create deal for qualified leads with property interest
    IF lead.property_type IS NOT NULL AND lead.budget_max > 0 THEN
        INSERT INTO deals (
            deal_type,
            status,
            title,
            price,
            client_id,
            created_by
        ) VALUES (
            CASE lead.interest_type
                WHEN 'buy' THEN 'sale'
                WHEN 'rent_short' THEN 'rent_short'
                WHEN 'rent_long' THEN 'rent_long'
                ELSE 'sale'
            END,
            'negotiation',
            CONCAT('Запрос: ', COALESCE(lead.property_type, 'недвижимость')),
            lead.budget_max,
            client_id,
            lead.assigned_to
        )
        RETURNING id INTO deal_id;

        UPDATE leads SET deal_id = deal_id WHERE id = lead_id;
    END IF;

COMMIT;
```

### Matching Existing Client (No Duplicate Creation)

Before creating a new Client, the conversion flow must check for existing Clients:

```python
CLIENT_MATCHING_FLOW = {
    "priority": [
        {
            "field": "phone",
            "match": "exact",
            "action": "link_to_existing",
        },
        {
            "field": "telegram_id",
            "match": "exact",
            "action": "link_to_existing",
        },
        {
            "field": "email",
            "match": "exact",
            "action": "link_to_existing",
        },
        {
            "field": "full_name + phone_partial",
            "match": "fuzzy (pg_trgm ≥ 0.8)",
            "action": "suggest_merge, require_review",
        },
    ],
    "no_match": "create_new",
}
```

### Lead → Deal Direct Path

Some leads convert directly to a Deal without an intermediate Client relationship:

- One-time transaction without ongoing relationship
- Anonymous buyer (legal requirement for deed only)
- Corporate entities that already exist in the system

In these cases, `leads.deal_id` is set directly without `leads.client_id`. The lead's `status` still transitions to `converted`.

---

## 4. `lead_events` Table

### DDL

```sql
CREATE TABLE lead_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,

    event_type VARCHAR(30) NOT NULL,
    -- status_changed | assigned | scored | qualified |
    -- converted | reopened | merged | note_added | auto_assigned

    -- Status changes
    from_status lead_status,
    to_status lead_status,

    -- Priority changes
    from_priority VARCHAR(10),
    to_priority VARCHAR(10),

    -- Score changes
    from_score FLOAT,
    to_score FLOAT,
    score_version VARCHAR(20),

    -- Assignment changes
    from_user_id UUID REFERENCES users(id),
    to_user_id UUID REFERENCES users(id),

    -- Context
    change_reason TEXT,
    changed_by UUID REFERENCES users(id),  -- NULL for system events

    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_lead_events_lead ON lead_events(lead_id);
CREATE INDEX idx_lead_events_type ON lead_events(event_type);
CREATE INDEX idx_lead_events_created ON lead_events(created_at DESC);
CREATE INDEX idx_lead_events_changed_by ON lead_events(changed_by);
```

### Event Types

| event_type | When | Required Fields |
|-----------|------|-----------------|
| `created` | Lead INSERT | to_status='new' |
| `status_changed` | Any status transition | from_status, to_status, change_reason |
| `assigned` | Agent assignment | from_user_id, to_user_id |
| `scored` | Score recalculation | from_score, to_score, score_version |
| `qualified` | Lead marked qualified | to_status='qualified', qualified_by |
| `converted` | Lead → Client | to_status='converted', client_id in metadata |
| `reopened` | Lost lead re-engaged | from_status='lost', to_status='qualifying' |
| `merged` | Two leads merged | metadata: {survivor_id, absorbed_id, merge_reason} |
| `auto_assigned` | System auto-assigned | to_user_id, metadata: {auto_reason} |
| `note_added` | Agent added note | metadata: {note_text} |

### Required Events Per Status Transition

Every status change MUST produce an event. This is enforced at the application layer:

```python
class LeadStatusMachine:
    """State machine enforcing valid transitions + event logging."""

    TRANSITIONS = {
        "new": ["contact_made", "spam", "lost"],
        "contact_made": ["qualifying", "new", "spam", "lost"],
        "qualifying": ["qualified", "contact_made", "lost", "spam"],
        "qualified": ["converted", "lost", "qualifying"],
        "converted": [],         # terminal
        "lost": ["qualifying"],  # reopening
        "spam": [],              # terminal
    }

    @contextmanager
    def transition(self, lead_id, to_status, changed_by, reason):
        lead = get_lead(lead_id)
        from_status = lead.status
        assert to_status in self.TRANSITIONS[from_status], \
            f"Invalid transition: {from_status} → {to_status}"

        yield  # perform business logic

        log_event(lead_id, "status_changed",
            from_status=from_status,
            to_status=to_status,
            changed_by=changed_by,
            change_reason=reason,
        )
```

---

## 5. Duplicate Prevention

### Before Creation

Every lead creation checks for duplicates across two dimensions:

```python
LEAD_DUPLICATE_CHECK = {
    "dimensions": [
        {
            "name": "exact_source_match",
            "query": """
                SELECT id, source, source_id, status, created_at
                FROM leads
                WHERE source = :source
                  AND source_id = :source_id
                  AND deleted_at IS NULL
            """,
            "action": "update_existing" if dedup_rule == "update_existing"
                      else "skip_if_active",
        },
        {
            "name": "phone_match",
            "query": """
                SELECT id, source, status, score, created_at
                FROM leads
                WHERE phone = :phone
                  AND status NOT IN ('converted', 'lost', 'spam')
                  AND deleted_at IS NULL
                ORDER BY score DESC
                LIMIT 1
            """,
            "action": "suggest_merge_or_link",
        },
        {
            "name": "telegram_id_match",
            "query": """
                SELECT id, source, status, score, created_at
                FROM leads
                WHERE telegram_id = :telegram_id
                  AND deleted_at IS NULL
                LIMIT 1
            """,
            "action": "create_new_with_link_note",
        },
        {
            "name": "existing_client_match",
            "query": """
                SELECT id, full_name, phone
                FROM clients
                WHERE phone = :phone
                   OR telegram_id = :telegram_id
                LIMIT 1
            """,
            "action": "link_lead_to_existing_client",
        },
    ],
}
```

### Client-Side Duplicate Prevention

The resolution layer (per ADR-0007) prevents duplicate Client creation. When a lead converts:

1. Check `clients` by phone (exact), telegram_id (exact), email (exact), full_name + phone (fuzzy)
2. Match → link lead to existing Client (`leads.client_id = existing.id`)
3. No match → create new Client

### Cross-Source Duplicate Resolution

When the same person appears as a lead from different sources:

```python
LEAD_MERGE_RULES = {
    "trigger": "phone_match or telegram_id_match between two active leads",
    "strategy": "keep_most_recently_updated, merge_source_metadata",
    "field_resolution": {
        "budget_min": "max",
        "budget_max": "max",
        "locations": "union",
        "notes": "concat_recent_first",
        "source": "keep_primary",         # first source is primary
        "source_id": "keep_primary",
        "source_metadata": "merge_jsonb",  # {source1: {...}, source2: {...}}
        "tags": "union",
        "score": "max",
        "priority": "max",
    },
    "event": "lead_merged",
    "metadata": {
        "survivor_id": "uuid",
        "absorbed_id": "uuid",   # soft-deleted after merge
        "merge_reason": "phone_match",
    },
}
```

---

## 6. Lead Reopening Flow

A `lost` lead can be reopened when the person re-engages.

### Reopening Triggers

| Trigger | Detection | New Status |
|---------|-----------|------------|
| Inbound message (Telegram) | New message from known chat_id | `qualifying` |
| Inbound call | Caller ID matches lead phone | `qualifying` |
| New Avito listing from same user | Same source_id with new timestamp | `new` (new lead created, old marked reopened) |
| Agent manually reopens | Agent action | `qualifying` |
| Referral from same person | Referral lead with same referrer + different subject | `new` (new lead created) |

### Reopening Transaction

```sql
BEGIN;
    UPDATE leads
    SET status = 'qualifying',
        previous_status = 'lost',
        status_changed_at = NOW(),
        priority = 'warm',
        score = GREATEST(score, 0.5),
        notes = CONCAT(notes, E'\n[Reopened ' , NOW()::text , ']')
    WHERE id = lead_id;

    INSERT INTO lead_events (lead_id, event_type,
        from_status, to_status, changed_by, change_reason)
    VALUES (lead_id, 'reopened',
        'lost', 'qualifying', NULL, 'Lead re-engaged');
COMMIT;
```

### Reopening Rules

| Rule | Value |
|------|-------|
| Max reopenings per lead | 3 (after 3rd → require manager approval) |
| Cooldown between reopenings | 7 days minimum |
| Score penalty per reopening | -0.1 (diminishing returns) |
| Auto-lost if no progress in | 14 days after reopening |

---

## 7. Spam Handling

### Spam Detection

| Signal | Detection | Confidence |
|--------|-----------|------------|
| Phone number in blocklist | Exact match against `blacklisted` clients | 1.0 — auto spam |
| Message pattern matching | Regex: "заработок", "кэшбэк", "быстрый доход" | 0.8 — suggest spam |
| Same phone + multiple leads in 1 hour | COUNT(leads) by phone > 5 in 60 min | 0.9 — auto spam |
| Agent manually flags | Agent action | 1.0 — immediate |

### Spam Transaction

```sql
BEGIN;
    UPDATE leads
    SET status = 'spam',
        previous_status = status,
        status_changed_at = NOW(),
        priority = 'parked',
        score = 0.0
    WHERE id = lead_id;

    INSERT INTO lead_events (lead_id, event_type,
        from_status, to_status, changed_by, change_reason)
    VALUES (lead_id, 'status_changed',
        :from_status, 'spam', :agent_id, :reason);

    -- If phone matches a non-spam lead, flag for review
    -- (possible phone number reuse by legitimate user)
    IF EXISTS (
        SELECT 1 FROM leads
        WHERE phone = :phone
          AND status NOT IN ('spam')
          AND id != :lead_id
    ) THEN
        INSERT INTO resolution_reviews (...)
        VALUES ('possible_spam_collision', ...);
    END IF;
COMMIT;
```

### Spam Recovery

- `spam` is a terminal state. No automatic recovery.
- Admin-only un-spam: hard-delete spam lead, create new lead with source=manual.
- Spam classifier training: all spam leads are sampled for ML model training.

---

## 8. Scoring Architecture

### Data Model Extensions

```sql
-- On the leads table (already included in §1):
-- score FLOAT DEFAULT 0.0
-- score_components JSONB DEFAULT '{}'
-- score_version VARCHAR(20)
-- last_scored_at TIMESTAMPTZ
```

### Score Components

```json
{
    "source_weight": 0.20,
    "budget_alignment": 0.15,
    "phone_provided": 0.10,
    "property_type_known": 0.10,
    "locations_known": 0.10,
    "response_history": 0.15,
    "agent_efficiency": 0.10,
    "market_timing": 0.10
}
```

### Priority Mapping

| Score Range | Priority | SLA | Auto-Assign |
|-------------|----------|-----|-------------|
| 0.80 – 1.00 | hot | Contact within 1 hour | Yes (round-robin) |
| 0.60 – 0.79 | warm | Contact within 24 hours | No (agent picks from queue) |
| 0.30 – 0.59 | cold | Contact within 72 hours | No |
| 0.00 – 0.29 | parked | No SLA | No (manual review) |

### Scoring Trigger Points

| Event | Scoring Trigger | Model | Latency |
|-------|----------------|-------|---------|
| Lead created | Immediate | Rule-based | < 10 ms |
| Lead updated (budget, location, property) | Immediate | Rule-based | < 10 ms |
| First contact made | Immediate | Rule-based + behavior | < 10 ms |
| Every hour (batch) | Scheduled | ML-based | < 1 sec per 1000 leads |
| Manual re-score | On demand | Full pipeline | < 5 sec |

### Scoring Event Logging

```sql
INSERT INTO lead_events (lead_id, event_type,
    from_score, to_score, score_version, changed_by, metadata)
VALUES (:lead_id, 'scored',
    :old_score, :new_score, :version, NULL,
    jsonb_build_object('components', :components_jsonb));
```

---

## 9. Knowledge Graph Integration

### New ENUM Values

```sql
ALTER TYPE node_type ADD VALUE 'lead';
ALTER TYPE edge_type ADD VALUE 'converts_to';
ALTER TYPE edge_type ADD VALUE 'assigned_to_agent';
ALTER TYPE edge_type ADD VALUE 'qualified_by_agent';
ALTER TYPE edge_type ADD VALUE 'generated_deal';
ALTER TYPE edge_type ADD VALUE 'from_communication';
```

### Graph Node Creation

On Lead INSERT, a graph node is automatically created (via trigger, per ADR-0008 pattern):

```
graph_nodes: {node_type='lead', entity_id=lead.id, label=lead.full_name OR lead.source||':'||lead.source_id}
```

### Graph Edge Creation

| Event | Edge | Source → Target | Source |
|-------|------|-----------------|--------|
| Lead created | `assigned_to_agent` | lead → user | fk (assigned_to) |
| Lead converted | `converts_to` | lead → client | conversion |
| Deal created from lead | `generated_deal` | lead → deal | conversion |
| Agent qualifies lead | `qualified_by_agent` | lead → user | fk (qualified_by) |
| Communication created | `from_communication` | lead → communication | extraction |

### Graph Query Patterns

```sql
-- Full lead pipeline: lead → client → deal
SELECT n1.label AS lead_name,
       n2.label AS client_name,
       n3.label AS deal_title,
       e1.edge_type,
       e2.edge_type
FROM graph_edges e1
JOIN graph_nodes n1 ON n1.id = e1.source_node_id
LEFT JOIN graph_nodes n2 ON n2.id = e1.target_node_id
LEFT JOIN graph_edges e2 ON e2.source_node_id = n2.id
LEFT JOIN graph_nodes n3 ON n3.id = e2.target_node_id
WHERE n1.node_type = 'lead'
  AND e1.edge_type = 'converts_to';

-- Agent lead load
SELECT u.full_name AS agent,
       COUNT(*) AS active_leads,
       AVG(l.score) AS avg_score
FROM leads l
JOIN users u ON u.id = l.assigned_to
WHERE l.status NOT IN ('converted', 'lost', 'spam')
  AND l.deleted_at IS NULL
GROUP BY u.full_name;
```

---

## 10. Files Affected

| File | Change |
|------|--------|
| `docs/domain/domain_model.md` | Add Lead entity section (11th entity) |
| `docs/domain/lead.md` | **NEW** — full Lead entity documentation |
| `docs/domain/client.md` | Update: remove 'lead' status, add lead_conversion source |
| `docs/domain/database_schema_v1.md` | Add leads table + lead_events table definitions |
| `backend/models/lead.py` | **NEW** — SQLAlchemy model (with score fields, NO clients.lead_id) |
| `backend/models/lead_event.py` | **NEW** — SQLAlchemy model |
| `backend/models/client.py` | Update: remove status='lead' from CHECK, remove lead_id |
| `backend/models/__init__.py` | Add Lead, LeadEvent imports |
| `backend/migrations/002_add_leads.py` | **NEW** — create tables + migrate existing lead-status clients |
| `docs/architecture/knowledge_graph.md` | Add `lead` node_type + 5 edge_types |
| `docs/adr/0012-architecture-freeze-v1.md` | Add ADR-0013 to Supersedes section |

---

## Impact

- **Documents affected:** 11 files (8 existing + 3 new)
- **Models affected:** 4 files (2 new + 2 updated)
- **Migration required:** Yes — `002_add_leads` (create leads, lead_events, migrate data, update clients CHECK constraint)
- **ADRs superseded:** None (additive change)
- **Re-implementation required:**
  - `LeadRepository` — CRUD + status transitions
  - `LeadService` — qualification, scoring, conversion
  - `LeadStatusMachine` — state machine with event logging
  - `TelegramHandler` — auto-create Lead, enrichment pipeline
  - `ClientRepository` — update matching to check leads before creating clients

---

## Risk Assessment

- **Breaking change:** Medium — `clients.status` CHECK constraint removes 'lead'. Queries filtering `WHERE status = 'lead'` must query `leads` table instead.
- **Data migration required:** Yes — existing Client records with `status = 'lead'` are migrated to `leads` table with their source and notes preserved.
- **Rollback plan:**
  1. Drop `lead_events` table
  2. Drop `leads` table
  3. Restore `'lead'` to `clients.status` CHECK constraint
  4. Copy lead data back to `clients` for any leads that were not yet converted
  5. Rebuild affected graph nodes (remove `lead` node_type)

---

## Alternatives Revisited

### Option A (Extend Client)
Rejected in v1. Review confirmed rejection — nullable columns > 90% null, conflicting lifecycles.

### Option B (JSONB metadata)
Rejected in v1. Review confirmed — JSONB cannot be indexed for scoring queries, no FK integrity.

### Option C (Separate Lead — this proposal)
**Accepted with revisions from review.** All 6 review changes incorporated.

---

## Consistency Check

| ADR | Check | Result |
|-----|-------|--------|
| ADR-0002 (Domain Model) | 10 → 11 entities | ✅ Additive. No entity boundaries changed. |
| ADR-0010 (Soft Delete) | `leads.deleted_at` | ✅ Present. |
| ADR-0007 (Entity Resolution) | Lead resolution by phone | ✅ Matching flow defined. |
| ADR-0008 (Knowledge Graph) | `lead` node + 5 edge types | ✅ Added to KG architecture. |
| ADR-0009 (Embedding Storage) | No embedding on leads for V1 | ✅ Lead scoring uses structured fields, not embeddings. Future: optional. |
| ADR-0012 (Architecture Freeze) | Change procedure followed | ✅ Proposal → Review → Revision → Acceptance. |

## Status

Accepted
