DO $$ 
DECLARE
    tbl text;
    start_date date;
    end_date date;
    part_name text;
BEGIN
    FOR tbl IN SELECT unnest(ARRAY['ai_call_log','agent_tool_calls','compliance_audits']) LOOP
        -- Check if already partitioned
        IF EXISTS (SELECT 1 FROM pg_class WHERE relname=tbl AND relkind='p') THEN
            RAISE NOTICE '% already partitioned, skipping', tbl;
            CONTINUE;
        END IF;
        -- Rename original table
        EXECUTE format('ALTER TABLE %I RENAME TO %I_old', tbl, tbl);
        -- Recreate as partitioned
        EXECUTE format('CREATE TABLE %I (LIKE %I_old INCLUDING DEFAULTS INCLUDING CONSTRAINTS) PARTITION BY RANGE (created_at)', tbl, tbl);
        -- Create partitions for 12 months
        FOR i IN 0..11 LOOP
            start_date := '2026-06-01'::date + (i || ' months')::interval;
            end_date := '2026-07-01'::date + (i || ' months')::interval;
            part_name := tbl || '_' || to_char(start_date, 'YYYY_MM');
            EXECUTE format('CREATE TABLE %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)', part_name, tbl, start_date, end_date);
        END LOOP;
        -- Copy data
        EXECUTE format('INSERT INTO %I SELECT * FROM %I_old', tbl, tbl);
        -- Drop old
        EXECUTE format('DROP TABLE %I_old', tbl);
        RAISE NOTICE '% partitioned with % rows', tbl, (SELECT count(*) FROM information_schema.tables WHERE table_name=tbl);
    END LOOP;
END $$;
