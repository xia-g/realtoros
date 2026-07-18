#!/usr/bin/env bash
#
# make_migration.sh — Alembic migration helper for Real Estate OS
#
# Usage:
#   ./make_migration.sh                  # autogenerate migration (requires running DB)
#   ./make_migration.sh "description"    # autogenerate with message
#   ./make_migration.sh --sql            # generate SQL offline (no DB connection needed)
#   ./make_migration.sh --upgrade        # apply pending migrations
#   ./make_migration.sh --downgrade -1   # rollback one migration
#   ./make_migration.sh --history        # show migration history
#   ./make_migration.sh --current        # show current revision
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
fi

MESSAGE="${1:-autogenerate}"

case "${1:-}" in
    --sql)
        # Offline migration generation
        shift || true
        MESSAGE="${1:-autogenerate}"
        echo "==> Generating offline SQL migration: $MESSAGE"
        alembic revision --autogenerate -m "$MESSAGE" --sql
        ;;
    --upgrade)
        echo "==> Applying all pending migrations"
        alembic upgrade head
        ;;
    --downgrade)
        REV="${2:--1}"
        echo "==> Rolling back $REV revision(s)"
        alembic downgrade "$REV"
        ;;
    --history)
        echo "==> Migration history"
        alembic history
        ;;
    --current)
        echo "==> Current revision"
        alembic current
        ;;
    *)
        # Default: autogenerate new migration
        echo "==> Autogenerating migration: $MESSAGE"
        alembic revision --autogenerate -m "$MESSAGE"
        echo "==> Migration generated. Review then apply with: alembic upgrade head"
        ;;
esac
