#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PSQL_BIN="${PSQL_BIN:-psql}"
SCHEMA_FILE="$ROOT_DIR/docker/postgres/init/02_telemetry.sql"
HOST_DATABASE_URL="${HOST_DATABASE_URL:-postgresql://artem@localhost:5433/artem}"
COMPOSE_DATABASE_URL="${COMPOSE_DATABASE_URL:-postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db}"

redact_url() {
  sed -E 's#(postgres(ql)?://[^:/@]+):[^@]*@#\1:***@#' <<<"$1"
}

if ! command -v "$PSQL_BIN" >/dev/null 2>&1; then
  echo "psql not found. Set PSQL_BIN or install PostgreSQL client tools." >&2
  exit 1
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  if PGCONNECT_TIMEOUT=2 "$PSQL_BIN" "$COMPOSE_DATABASE_URL" -Atqc "SELECT 1" >/dev/null 2>&1; then
    DATABASE_URL="$COMPOSE_DATABASE_URL"
  else
    DATABASE_URL="$HOST_DATABASE_URL"
  fi
fi

echo "Applying SafeRoute telemetry schema to $(redact_url "$DATABASE_URL")"
if ! "$PSQL_BIN" "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$SCHEMA_FILE"; then
  echo "" >&2
  echo "Telemetry schema apply failed." >&2
  echo "Start Postgres first, or point DATABASE_URL at the running SafeRoute database." >&2
  echo "For the compose DB, use:" >&2
  echo "  docker compose up db" >&2
  echo "  DATABASE_URL=postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db npm run db:telemetry-schema" >&2
  exit 1
fi
