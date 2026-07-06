-- verify_partitions.sql — Validate partition setup
-- Run: sudo -u postgres psql -d realtoros -f backend/scripts/verify_partitions.sql

-- 1. Check partitioned tables exist
SELECT
    p.relname AS table_name,
    pt.partstrat AS strategy,
    CASE pt.partstrat
        WHEN 'r' THEN 'RANGE'
        WHEN 'l' THEN 'LIST'
        WHEN 'h' THEN 'HASH'
    END AS strategy_desc
FROM pg_class p
JOIN pg_partitioned_table pt ON pt.partrelid = p.oid
WHERE p.relname IN ('ai_call_log', 'agent_tool_calls', 'compliance_audits');

-- 2. Count partitions per table
SELECT
    p.relname AS table_name,
    count(i.inhrelid) AS partition_count,
    min(c.relname) AS first_partition,
    max(c.relname) AS last_partition
FROM pg_class p
JOIN pg_partitioned_table pt ON pt.partrelid = p.oid
LEFT JOIN pg_inherits i ON i.inhparent = p.oid
LEFT JOIN pg_class c ON c.oid = i.inhrelid
WHERE p.relname IN ('ai_call_log', 'agent_tool_calls', 'compliance_audits')
GROUP BY p.relname;

-- 3. List all partitions
SELECT
    c.relname AS partition_name,
    pg_get_expr(c.relpartbound, c.oid) AS partition_range
FROM pg_class p
JOIN pg_inherits i ON i.inhparent = p.oid
JOIN pg_class c ON c.oid = i.inhrelid
WHERE p.relname IN ('ai_call_log', 'agent_tool_calls', 'compliance_audits')
ORDER BY p.relname, c.relname;

-- 4. Verify PRIMARY KEY includes partition column
SELECT
    conrelid::regclass AS table_name,
    conname AS constraint_name,
    pg_get_constraintdef(oid) AS constraint_def
FROM pg_constraint
WHERE contype = 'p'
  AND conrelid::regclass::text IN ('ai_call_log', 'agent_tool_calls', 'compliance_audits');

-- Expected:
-- All 3 tables should appear in query 1
-- Each should have 12+ partitions (query 2)
-- First partition: *_2026_01, Last: *_2026_12 (query 2)
-- Partition ranges should cover full 2026 (query 3)
-- PK should include (id, created_at) (query 4)
