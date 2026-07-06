-- Execute partitioning — run via: sudo -u postgres psql -d realtoros -f execute_partitioning.sql
-- PostgreSQL 17 required (IF NOT EXISTS for CREATE TYPE)

-- Step 1: Run all migrations
-- cd /home/xiag/real-estate-os && source venv/bin/activate && python -m alembic upgrade head

-- Step 2: Create partitions AFTER migrations complete

DO $$
DECLARE
    tbl text;
    part_name text;
    start_date date;
    end_date date;
    month_offset int;
BEGIN
    FOREACH tbl IN ARRAY ARRAY['ai_call_log', 'agent_tool_calls', 'compliance_audits']
    LOOP
        -- Check if table exists
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = tbl) THEN
            -- Check if already partitioned
            IF NOT EXISTS (
                SELECT 1 FROM pg_class p
                JOIN pg_partitioned_table pt ON pt.partrelid = p.oid
                WHERE p.relname = tbl
            ) THEN
                RAISE NOTICE 'Table % is not partitioned. Create partition migration first.', tbl;
                CONTINUE;
            END IF;

            -- Create partitions for next 12 months
            FOR month_offset IN 0..11 LOOP
                start_date := date_trunc('month', now()) + (month_offset || ' months')::interval;
                end_date := start_date + interval '1 month';
                part_name := tbl || '_' || to_char(start_date, 'YYYY_MM');

                BEGIN
                    EXECUTE format(
                        'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I
                         FOR VALUES FROM (%L) TO (%L)',
                        part_name, tbl, start_date, end_date
                    );
                    RAISE NOTICE 'Created partition: %', part_name;
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'Skipped: % (%)', part_name, SQLERRM;
                END;
            END LOOP;
        ELSE
            RAISE NOTICE 'Table % does not exist. Run migrations first.', tbl;
        END IF;
    END LOOP;
END $$;

-- Step 3: Verify
SELECT tablename,
       (SELECT count(*) FROM pg_inherits i
        JOIN pg_class p ON p.oid = i.inhparent
        WHERE p.relname = tablename) AS partition_count
FROM pg_catalog.pg_tables
WHERE tablename IN ('ai_call_log', 'agent_tool_calls', 'compliance_audits')
ORDER BY tablename;

-- Expected output:
-- ai_call_log        | 12
-- agent_tool_calls   | 12
-- compliance_audits  | 12
