-- create_partitions.sql — Convert audit tables to native PG partitioning
-- Run: sudo -u postgres psql -d realtoros -f backend/scripts/create_partitions.sql
--
-- Actual column schemas extracted from migrations 006 (ai_call_log), 011 (agent_tool_calls), 017 (compliance_audits)

BEGIN;

-- === ai_call_log (18 columns, from migration 006) ===
ALTER TABLE ai_call_log RENAME TO ai_call_log_old;

CREATE TABLE ai_call_log (
    id UUID DEFAULT gen_random_uuid(),
    correlation_id VARCHAR,
    request_id VARCHAR,
    user_id UUID,
    tenant_id UUID,
    provider VARCHAR,
    model_name VARCHAR,
    task_type VARCHAR,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    cost_usd NUMERIC,
    latency_ms INTEGER,
    status VARCHAR,
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- === agent_tool_calls (11 columns, from migration 011) ===
ALTER TABLE agent_tool_calls RENAME TO agent_tool_calls_old;

CREATE TABLE agent_tool_calls (
    id UUID DEFAULT gen_random_uuid(),
    correlation_id VARCHAR,
    session_id UUID,
    user_id UUID,
    tool_name VARCHAR,
    input_hash VARCHAR,
    duration_ms INTEGER,
    success BOOLEAN,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- === compliance_audits (12 columns, from migration 017) ===
ALTER TABLE compliance_audits RENAME TO compliance_audits_old;

CREATE TABLE compliance_audits (
    id UUID DEFAULT gen_random_uuid(),
    deal_id UUID,
    correlation_id VARCHAR,
    audit_type VARCHAR,
    score NUMERIC,
    result JSONB,
    risk_level VARCHAR,
    blocking_issues JSONB,
    used_regulations JSONB,
    used_documents JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Create monthly partitions (current month + 12)
DO $$
DECLARE
    tbl TEXT;
    part_name TEXT;
    start_date DATE;
    end_date DATE;
    i INT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY['ai_call_log', 'agent_tool_calls', 'compliance_audits']
    LOOP
        FOR i IN 0..11 LOOP
            start_date := date_trunc('month', now()) + (i || ' months')::INTERVAL;
            end_date := start_date + INTERVAL '1 month';
            part_name := tbl || '_' || TO_CHAR(start_date, 'YYYY_MM');
            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
                part_name, tbl, start_date, end_date
            );
        END LOOP;
    END LOOP;
END $$;

-- Migrate data
INSERT INTO ai_call_log 
SELECT * FROM ai_call_log_old ON CONFLICT DO NOTHING;
INSERT INTO agent_tool_calls 
SELECT * FROM agent_tool_calls_old ON CONFLICT DO NOTHING;
INSERT INTO compliance_audits 
SELECT * FROM compliance_audits_old ON CONFLICT DO NOTHING;

-- Drop old tables
DROP TABLE ai_call_log_old;
DROP TABLE agent_tool_calls_old;
DROP TABLE compliance_audits_old;

COMMIT;
