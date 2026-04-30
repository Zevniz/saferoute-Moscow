#!/usr/bin/env bash
set -euo pipefail

DATABASE_URL="${DATABASE_URL:-postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db}"
PYTHON_BIN="${PYTHON_BIN:-./venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="${PYTHON_BIN_FALLBACK:-python3}"
fi

current="$(DATABASE_URL="$DATABASE_URL" "$PYTHON_BIN" -m alembic current 2>/dev/null | awk '{print $1}' | tail -n 1 || true)"
head="$(DATABASE_URL="$DATABASE_URL" "$PYTHON_BIN" -m alembic heads 2>/dev/null | awk '{print $1}' | tail -n 1 || true)"

if [[ -z "$head" ]]; then
  echo "fail: Alembic head could not be determined. Is alembic installed?" >&2
  exit 1
fi

if [[ "$current" != "$head" ]]; then
  echo "fail: database migration version is not at head (current=${current:-none}, head=$head)." >&2
  echo "Run: npm run db:migrate" >&2
  exit 1
fi

echo "Migration check passed: $current"
