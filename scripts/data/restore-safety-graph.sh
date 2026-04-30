#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_DATABASE_URL="${TARGET_DATABASE_URL:-postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db}"
GRAPH_DUMP_FILE="${SAFEROUTE_GRAPH_DUMP_PATH:-${GRAPH_DUMP_FILE:-$ROOT_DIR/data/graph/moscow_network.dump}}"
FORCE_DB_IMPORT="${FORCE_DB_IMPORT:-false}"
ALLOW_UNVERIFIED_GRAPH_DUMP="${ALLOW_UNVERIFIED_GRAPH_DUMP:-false}"
SAFEROUTE_ENV_VALUE="${SAFEROUTE_ENV:-${ENVIRONMENT:-local}}"
PSQL_BIN="${PSQL_BIN:-psql}"
PG_RESTORE_BIN="${PG_RESTORE_BIN:-pg_restore}"

redact_url() {
  printf "%s" "$1" | sed -E 's#(postgres(ql)?://[^:/@]+:)[^@]+@#\1***@#'
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "$1 is not available. Install PostgreSQL client tools or set the matching *_BIN env." >&2
    exit 1
  fi
}

query_scalar() {
  PGCONNECT_TIMEOUT=5 "$PSQL_BIN" "$TARGET_DATABASE_URL" -Atqc "$1"
}

wait_for_db() {
  echo "Waiting for target PostGIS on $(redact_url "$TARGET_DATABASE_URL") ..."
  for _ in $(seq 1 90); do
    if "$PSQL_BIN" "$TARGET_DATABASE_URL" -Atqc "SELECT 1" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "Target PostGIS did not become ready in time." >&2
  exit 1
}

cd "$ROOT_DIR"
require_cmd "$PSQL_BIN"
require_cmd "$PG_RESTORE_BIN"

if ! GRAPH_DUMP_FILE="$GRAPH_DUMP_FILE" bash scripts/data/check-graph-dump.sh; then
  normalized_env="$(printf "%s" "$SAFEROUTE_ENV_VALUE" | tr '[:upper:]' '[:lower:]')"
  if [[ "$ALLOW_UNVERIFIED_GRAPH_DUMP" == "true" && "$normalized_env" != "production" ]]; then
    echo "warn: ALLOW_UNVERIFIED_GRAPH_DUMP=true; proceeding without verified graph manifest in non-production env '$SAFEROUTE_ENV_VALUE'." >&2
  else
    echo "fail: graph dump verification failed; restore is blocked." >&2
    echo "Set SAFEROUTE_GRAPH_DUMP_PATH or GRAPH_DUMP_FILE to a real dump with a valid manifest." >&2
    echo "For local-only recovery, ALLOW_UNVERIFIED_GRAPH_DUMP=true is allowed outside production." >&2
    exit 1
  fi
fi

wait_for_db

if [[ "$FORCE_DB_IMPORT" != "true" ]]; then
  existing="$(query_scalar "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='moscow_network');" 2>/dev/null || true)"
  if [[ "$existing" == "t" ]]; then
    echo "Target already has public.moscow_network; skipping restore. Set FORCE_DB_IMPORT=true to reimport from the dump."
    DATABASE_URL="$TARGET_DATABASE_URL" PSQL_BIN="$PSQL_BIN" bash scripts/check-graph-data.sh
    exit 0
  fi
fi

if [[ "$FORCE_DB_IMPORT" == "true" ]]; then
  echo "FORCE_DB_IMPORT=true: replacing target graph in $(redact_url "$TARGET_DATABASE_URL")"
  "$PSQL_BIN" "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
DROP MATERIALIZED VIEW IF EXISTS public.moscow_network_nodes;
DROP TABLE IF EXISTS public.moscow_network CASCADE;
SQL
fi

echo "Restoring real graph dump into $(redact_url "$TARGET_DATABASE_URL")"
"$PG_RESTORE_BIN" \
  --no-owner \
  --no-privileges \
  --dbname="$TARGET_DATABASE_URL" \
  "$GRAPH_DUMP_FILE"

echo "Preparing production-safe routing graph metadata..."
"$PSQL_BIN" "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/prepare-production-db.sql

DATABASE_URL="$TARGET_DATABASE_URL" PSQL_BIN="$PSQL_BIN" bash scripts/check-graph-data.sh
