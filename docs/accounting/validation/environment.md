# Validation Environment

## Topology

```
┌──────────────┐     ┌──────────────────┐
│  PostgreSQL   │◄────│  Backend (uvicorn)│
│  :5432        │     │  :8000            │
└──────────────┘     └────────┬─────────┘
                              │
                     ┌────────▼─────────┐
                     │  Frontend (Next)  │
                     │  :3000            │
                     └──────────────────┘
```

## One-Command Startup

```bash
# Full stack
bash scripts/validate/bootstrap.sh

# Clean reset (drops all accounting tables, re-runs migrations)
bash scripts/validate/reset.sh

# Seed validation dataset
bash scripts/validate/seed.sh

# Run all validation stages
bash scripts/validate/run_all.sh
```

## Health Checks

| Component | Check | Expected |
|-----------|-------|----------|
| PostgreSQL | `pg_isready` | accepting connections |
| Backend | `curl :8000/health` | 200 OK |
| Frontend | `curl :3000` | 200 OK |
| Migrations | `alembic current` | head: `034_control_plane_schema` |

## Seeded Data

| Entity | Count | Description |
|--------|-------|-------------|
| Tax Policies | 3 | USN_D, USN_DR, GENERAL |
| Tax Rules | 18 | account→register mappings |
| Report Templates | 3 | USN_DECLARATION, USN_DR_DECLARATION, VAT_3 |
| Tax Regime | 1 | company with usn_income |
| Tax Period | 1 | 2026 yearly, open |

## Teardown

```bash
# Kill services
kill $(cat /tmp/validate.pids) 2>/dev/null || true

# Drop all
bash scripts/validate/reset.sh

# Full cleanup
sudo service postgresql stop 2>/dev/null || true
```
