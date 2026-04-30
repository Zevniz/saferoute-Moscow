#!/usr/bin/env bash
set -euo pipefail

DATABASE_URL="${DATABASE_URL:-postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db}"
PYTHON_BIN="${PYTHON_BIN:-./venv/bin/python}"

redact_url() {
  sed -E 's#(postgres(ql)?://[^:/@]+):[^@]*@#\1:***@#' <<<"$1"
}

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="${PYTHON_BIN_FALLBACK:-python3}"
fi

echo "Running SafeRoute app-owned migrations against $(redact_url "$DATABASE_URL")"
DATABASE_URL="$DATABASE_URL" "$PYTHON_BIN" -m alembic upgrade head
