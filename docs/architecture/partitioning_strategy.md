# Partitioning Strategy

**Date:** 2026-06-10
**Target Tables:** ai_call_log, agent_tool_calls, compliance_audits

---

## Strategy

- **Type:** RANGE partitioning by `created_at`
- **Granularity:** Monthly
- **Retention:** 12 months (rolling)
- **Auto-creation:** cron job runs monthly

## DDL

```sql
-- Step 1: Rename old tables
ALTER TABLE ai_call_log RENAME TO ai_call_log_old;
ALTER TABLE agent_tool_calls RENAME TO agent_tool_calls_old;
ALTER TABLE compliance_audits RENAME TO compliance_audits_old;

-- Step 2: Create partitioned tables (same schema)
CREATE TABLE ai_call_log (
    id UUID DEFAULT gen_random_uuid(),
    session_id UUID,
    user_id UUID,
    model TEXT,
    prompt_tokens INT,
    completion_tokens INT,
    duration_ms INT,
    cost NUMERIC(10,6),
    correlation_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE TABLE agent_tool_calls (
    id UUID DEFAULT gen_random_uuid(),
    session_id UUID,
    user_id UUID,
    tool_name TEXT,
    input JSONB,
    output JSONB,
    duration_ms INT,
    success BOOLEAN,
    correlation_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE TABLE compliance_audits (
    id UUID DEFAULT gen_random_uuid(),
    deal_id UUID,
    audit_type TEXT,
    score NUMERIC(5,2),
    risk_level TEXT,
    details JSONB,
    correlation_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Step 3: Create initial partitions (12 months)
SELECT create_monthly_partitions('ai_call_log', '2026-01-01', 12);
SELECT create_monthly_partitions('agent_tool_calls', '2026-01-01', 12);
SELECT create_monthly_partitions('compliance_audits', '2026-01-01', 12);

-- Step 4: Migrate data
INSERT INTO ai_call_log SELECT * FROM ai_call_log_old;
INSERT INTO agent_tool_calls SELECT * FROM agent_tool_calls_old;
INSERT INTO compliance_audits SELECT * FROM compliance_audits_old;

-- Step 5: Drop old tables
DROP TABLE ai_call_log_old;
DROP TABLE agent_tool_calls_old;
DROP TABLE compliance_audits_old;
```

## Auto-Creation Function

```sql
CREATE OR REPLACE FUNCTION create_monthly_partitions(
    table_name TEXT,
    start_date DATE,
    months INT DEFAULT 12
) RETURNS void AS $$
DECLARE
    i INT;
    part_name TEXT;
    part_start DATE;
    part_end DATE;
BEGIN
    FOR i IN 0..months-1 LOOP
        part_start := start_date + (i || ' months')::INTERVAL;
        part_end := part_start + INTERVAL '1 month';
        part_name := table_name || '_' || TO_CHAR(part_start, 'YYYY_MM');
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I
             FOR VALUES FROM (%L) TO (%L)',
            part_name, table_name, part_start, part_end
        );
    END LOOP;
END;
$$ LANGUAGE plpgsql;
```

## Cron (auto-creation next month)

```cron
0 0 1 * * psql -d realtoros -c "SELECT create_monthly_partitions('ai_call_log', date_trunc('month', now() + interval '12 months')::date, 1)"
0 0 1 * * psql -d realtoros -c "SELECT create_monthly_partitions('agent_tool_calls', date_trunc('month', now() + interval '12 months')::date, 1)"
0 0 1 * * psql -d realtoros -c "SELECT create_monthly_partitions('compliance_audits', date_trunc('month', now() + interval '12 months')::date, 1)"
```

## Retention Policy

```sql
-- Drop partitions older than 12 months
CREATE OR REPLACE FUNCTION drop_old_partitions(retention_months INT DEFAULT 12)
RETURNS void AS $$
DECLARE
    r RECORD;
    cutoff_date DATE;
BEGIN
    cutoff_date := date_trunc('month', now() - (retention_months || ' months')::INTERVAL);
    FOR r IN (
        SELECT inhrelid::REGCLASS::TEXT AS partition_name
        FROM pg_inherits i
        JOIN pg_class p ON p.oid = i.inhparent
        WHERE p.relname IN ('ai_call_log', 'agent_tool_calls', 'compliance_audits')
    ) LOOP
        IF r.partition_name ~ '_(\d{4})_(\d{2})$' THEN
            EXECUTE format('DROP TABLE IF EXISTS %I', r.partition_name);
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;
```

## Migration Plan

1. Run `backend/scripts/create_partitions.sql` on realtoros database
2. Monitor: `SELECT tablename, partition_count FROM verify_partitions()`
3. Add cron job for auto-creation
4. Add cron job for retention cleanup
