#!/usr/bin/env bash
set -euo pipefail

PSQL_BIN="${PSQL_BIN:-psql}"
SOURCE_DATABASE_URL="${SOURCE_DATABASE_URL:-postgresql://artem@localhost:5433/artem}"
MIN_GRAPH_ROWS="${MIN_GRAPH_ROWS:-1}"

redact_url() {
  printf "%s" "$1" | sed -E 's#(postgres(ql)?://[^:/@]+:)[^@]+@#\1***@#'
}

if ! command -v "$PSQL_BIN" >/dev/null 2>&1; then
  echo "psql not found. Set PSQL_BIN or install PostgreSQL client tools." >&2
  exit 1
fi

query_scalar() {
  PGCONNECT_TIMEOUT=5 "$PSQL_BIN" "$SOURCE_DATABASE_URL" -Atqc "$1"
}

query_table() {
  PGCONNECT_TIMEOUT=5 "$PSQL_BIN" "$SOURCE_DATABASE_URL" -c "$1"
}

fail_check() {
  echo "fail: $1" >&2
  echo "" >&2
  echo "Graph source check failed for $(redact_url "$SOURCE_DATABASE_URL")." >&2
  echo "Set SOURCE_DATABASE_URL to a real database that contains public.moscow_network before running npm run bootstrap:self-hosted." >&2
  echo "This script never creates fake graph data." >&2
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

require_equals() {
  local query="$1"
  local expected="$2"
  local label="$3"
  local value
  if ! value="$(query_scalar "$query" 2>/dev/null)"; then
    fail_check "$label could not be checked"
  fi
  if [[ "$value" == "$expected" ]]; then
    echo "ok: $label ($value)"
    return
  fi
  fail_check "$label expected $expected, got $value"
}

echo "Checking SafeRoute graph source in $(redact_url "$SOURCE_DATABASE_URL")"

require_count_at_least \
  "SELECT count(*) FROM pg_extension WHERE extname = 'postgis';" \
  1 \
  "PostGIS extension"

require_true \
  "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='moscow_network');" \
  "table public.moscow_network exists"

require_count_at_least \
  "SELECT count(*) FROM public.moscow_network;" \
  "$MIN_GRAPH_ROWS" \
  "public.moscow_network rows"

require_count_at_least \
  "SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='moscow_network' AND column_name IN ('id','u','v','highway','length','safety_weight','geometry');" \
  7 \
  "required source columns"

require_equals \
  "SELECT count(*) = count(id) AND count(*) = count(u) AND count(*) = count(v) FROM public.moscow_network;" \
  "t" \
  "routing node/id columns are populated"

require_equals \
  "SELECT count(*) = count(geometry) FROM public.moscow_network;" \
  "t" \
  "all source rows have geometry"

require_equals \
  "SELECT COALESCE((SELECT ST_SRID(geometry)::text FROM public.moscow_network WHERE geometry IS NOT NULL LIMIT 1), 'missing');" \
  "4326" \
  "source geometry SRID"

require_equals \
  "SELECT count(*) = count(safety_weight) FROM public.moscow_network;" \
  "t" \
  "all source rows have safety_weight"

require_true \
  "SELECT NOT EXISTS (SELECT 1 FROM public.moscow_network WHERE length IS NULL OR length < 0 OR ST_IsEmpty(geometry));" \
  "routing-prep eligible length and geometry values"

echo
echo "Source graph coverage:"
query_table "SELECT
  count(*) AS edges,
  count(*) FILTER (WHERE highway IS NOT NULL) AS highway_count,
  count(*) FILTER (WHERE safety_weight IS NOT NULL) AS safety_weight_count,
  min(safety_weight) AS min_safety_weight,
  max(safety_weight) AS max_safety_weight
FROM public.moscow_network;"

echo "Graph source check passed."
