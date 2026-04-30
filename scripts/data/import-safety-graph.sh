#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.yml}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-}"
COMPOSE_OVERRIDE_FILE="${COMPOSE_OVERRIDE_FILE:-}"
SOURCE_DATABASE_URL="${SOURCE_DATABASE_URL:-postgresql://artem@localhost:5433/artem}"
TARGET_DATABASE_URL="${TARGET_DATABASE_URL:-postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db}"
TARGET_TABLE="${TARGET_TABLE:-public.moscow_network}"
FORCE_DB_IMPORT="${FORCE_DB_IMPORT:-false}"
PSQL_BIN="${PSQL_BIN:-$(command -v psql)}"
if [[ -x "/Applications/Postgres.app/Contents/Versions/latest/bin/pg_dump" ]]; then
  PG_DUMP_BIN="${PG_DUMP_BIN:-/Applications/Postgres.app/Contents/Versions/latest/bin/pg_dump}"
else
  PG_DUMP_BIN="${PG_DUMP_BIN:-$(command -v pg_dump)}"
fi

redact_url() {
  printf "%s" "$1" | sed -E 's#(postgres(ql)?://[^:/@]+:)[^@]+@#\1***@#'
}

require_cmd() {
  local command_path="$1"
  local label="$2"
  if [[ -n "$command_path" && ( -x "$command_path" || -n "$(command -v "$command_path" 2>/dev/null)" ) ]]; then
    return
  fi
  if [[ -z "$command_path" ]]; then
    echo "$label is not available. Install PostgreSQL client tools or set ${label}_BIN." >&2
    exit 1
  fi
  echo "$label is not executable or available on PATH: $command_path" >&2
  exit 1
}

compose() {
  local args=(-f "$COMPOSE_FILE")
  if [[ -n "$COMPOSE_OVERRIDE_FILE" ]]; then
    args+=(-f "$COMPOSE_OVERRIDE_FILE")
  fi
  if [[ -n "$COMPOSE_PROJECT_NAME" ]]; then
    args+=(-p "$COMPOSE_PROJECT_NAME")
  fi
  docker compose "${args[@]}" "$@"
}

wait_for_db() {
  echo "Waiting for compose PostGIS on $(redact_url "$TARGET_DATABASE_URL") ..."
  for _ in $(seq 1 90); do
    if "$PSQL_BIN" "$TARGET_DATABASE_URL" -Atqc "SELECT 1" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "Compose PostGIS did not become ready in time." >&2
  exit 1
}

table_exists() {
  "$PSQL_BIN" "$TARGET_DATABASE_URL" -Atqc \
    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='moscow_network');"
}

verify_target() {
  DATABASE_URL="$TARGET_DATABASE_URL" PSQL_BIN="$PSQL_BIN" bash scripts/check-graph-data.sh
}

validate_source_graph() {
  echo "Validating real graph source before importing: $(redact_url "$SOURCE_DATABASE_URL")"
  SOURCE_DATABASE_URL="$SOURCE_DATABASE_URL" PSQL_BIN="$PSQL_BIN" bash scripts/check-graph-source.sh
}

cd "$ROOT_DIR"

require_cmd "$PSQL_BIN" "PSQL"
require_cmd "$PG_DUMP_BIN" "PG_DUMP"

compose up -d db >/dev/null
wait_for_db

if [[ "$FORCE_DB_IMPORT" != "true" && "$(table_exists)" == "t" ]]; then
  echo "Compose DB already has public.moscow_network; skipping import."
else
  validate_source_graph
  echo "Importing $TARGET_TABLE from host DB into compose PostGIS..."
  "$PSQL_BIN" "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
DROP MATERIALIZED VIEW IF EXISTS public.moscow_network_nodes;
DROP TABLE IF EXISTS public.moscow_network CASCADE;
SQL

  "$PG_DUMP_BIN" "$SOURCE_DATABASE_URL" \
    --schema-only \
    --no-owner \
    --no-privileges \
    --table="$TARGET_TABLE" \
    | sed '/^SET transaction_timeout =/d' \
    | "$PSQL_BIN" "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1

  "$PG_DUMP_BIN" "$SOURCE_DATABASE_URL" \
    --data-only \
    --no-owner \
    --no-privileges \
    --table="$TARGET_TABLE" \
    | sed '/^SET transaction_timeout =/d' \
    | "$PSQL_BIN" "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1
fi

echo "Preparing production-safe routing graph metadata..."
"$PSQL_BIN" "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/prepare-production-db.sql

verify_target
