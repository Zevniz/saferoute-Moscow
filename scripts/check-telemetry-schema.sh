#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PSQL_BIN="${PSQL_BIN:-psql}"
HOST_DATABASE_URL="${HOST_DATABASE_URL:-postgresql://artem@localhost:5433/artem}"
COMPOSE_DATABASE_URL="${COMPOSE_DATABASE_URL:-postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db}"

redact_url() {
  printf "%s" "$1" | sed -E 's#(postgres(ql)?://[^:/@]+:)[^@]+@#\1***@#'
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

query_scalar() {
  PGCONNECT_TIMEOUT=3 "$PSQL_BIN" "$DATABASE_URL" -Atqc "$1"
}

fail_check() {
  echo "fail: $1" >&2
  echo "" >&2
  echo "Telemetry schema check failed for $(redact_url "$DATABASE_URL")." >&2
  echo "Apply the idempotent schema first:" >&2
  echo "  DATABASE_URL=$(redact_url "$DATABASE_URL") npm run db:telemetry-schema" >&2
  exit 1
}

require_true() {
  local query="$1"
  local label="$2"
  local value
  if ! value="$(query_scalar "$query" 2>/dev/null)"; then
    fail_check "$label could not be checked"
  fi
  if [[ "$value" == "t" ]]; then
    echo "ok: $label"
    return
  fi
  fail_check "$label is missing"
}

require_count_at_least() {
  local query="$1"
  local expected="$2"
  local label="$3"
  local value
  if ! value="$(query_scalar "$query" 2>/dev/null)"; then
    fail_check "$label could not be checked"
  fi
  if [[ "$value" =~ ^[0-9]+$ && "$value" -ge "$expected" ]]; then
    echo "ok: $label ($value/$expected)"
    return
  fi
  fail_check "$label is incomplete ($value/$expected)"
}

cd "$ROOT_DIR"

echo "Checking SafeRoute telemetry schema in $(redact_url "$DATABASE_URL")"

require_true \
  "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='sidewalk_samples' AND table_type='BASE TABLE');" \
  "table public.sidewalk_samples exists"

require_true \
  "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='sidewalk_cell_aggregates' AND table_type='BASE TABLE');" \
  "table public.sidewalk_cell_aggregates exists"

require_count_at_least \
  "SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='sidewalk_samples' AND column_name IN ('id','device_id','captured_at','lat','lon','speed_mps','source','surface_score','vibration_rms','obstacle_score','gps_accuracy_m','model_version','h3_cell','h3_resolution','quality_score','confidence','created_at');" \
  17 \
  "sidewalk_samples expected columns"

require_count_at_least \
  "SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='sidewalk_cell_aggregates' AND column_name IN ('h3_cell','h3_resolution','centroid_lat','centroid_lon','sample_count','quality_sum','obstacle_sum','vibration_sum','confidence_sum','first_seen_at','last_seen_at');" \
  11 \
  "sidewalk_cell_aggregates expected columns"

require_count_at_least \
  "SELECT count(*) FROM information_schema.table_constraints WHERE table_schema='public' AND table_name IN ('sidewalk_samples','sidewalk_cell_aggregates') AND constraint_type='PRIMARY KEY';" \
  2 \
  "telemetry primary keys"

require_count_at_least \
  "SELECT count(*) FROM pg_indexes WHERE schemaname='public' AND indexname IN ('sidewalk_samples_captured_at_idx','sidewalk_samples_h3_idx','sidewalk_cell_aggregates_bbox_idx');" \
  3 \
  "telemetry indexes"

echo "Telemetry schema check passed."
