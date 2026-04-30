#!/usr/bin/env bash
set -euo pipefail

PSQL_BIN="${PSQL_BIN:-psql}"
HOST_DATABASE_URL="${HOST_DATABASE_URL:-postgresql://artem@localhost:5433/artem}"
COMPOSE_DATABASE_URL="${COMPOSE_DATABASE_URL:-postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db}"
MIN_GRAPH_ROWS="${MIN_GRAPH_ROWS:-1}"

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
  PGCONNECT_TIMEOUT=5 "$PSQL_BIN" "$DATABASE_URL" -Atqc "$1"
}

query_table() {
  PGCONNECT_TIMEOUT=5 "$PSQL_BIN" "$DATABASE_URL" -c "$1"
}

fail_check() {
  echo "fail: $1" >&2
  echo "" >&2
  echo "Graph data check failed for $(redact_url "$DATABASE_URL")." >&2
  echo "Restore/import real graph data before self-hosted route verification:" >&2
  echo "  npm run self-hosted:preflight" >&2
  echo "  npm run bootstrap:self-hosted" >&2
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

echo "Checking SafeRoute graph data in $(redact_url "$DATABASE_URL")"

require_count_at_least \
  "SELECT count(*) FROM pg_extension WHERE extname IN ('postgis','pgrouting');" \
  2 \
  "PostGIS and pgRouting extensions"

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
  "required moscow_network columns"

require_equals \
  "SELECT count(*) = count(geometry) FROM public.moscow_network;" \
  "t" \
  "all moscow_network rows have geometry"

require_equals \
  "SELECT COALESCE((SELECT ST_SRID(geometry)::text FROM public.moscow_network WHERE geometry IS NOT NULL LIMIT 1), 'missing');" \
  "4326" \
  "moscow_network geometry SRID"

require_count_at_least \
  "SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='moscow_network' AND column_name IN ('cost_walk_safe','cost_bike_safe','cost_car_safe','source_x','source_y','target_x','target_y');" \
  7 \
  "prepared routing/A* columns"

require_true \
  "SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname='public' AND c.relname='moscow_network_nodes' AND c.relkind IN ('r','m'));" \
  "relation public.moscow_network_nodes exists"

require_count_at_least \
  "SELECT count(*) FROM public.moscow_network_nodes;" \
  1 \
  "public.moscow_network_nodes rows"

require_count_at_least \
  "SELECT count(*) FROM pg_indexes WHERE schemaname='public' AND indexname IN ('moscow_network_geom_idx','moscow_network_u_idx','moscow_network_v_idx','moscow_network_highway_idx','moscow_network_nodes_geom_idx');" \
  5 \
  "required graph indexes"

echo
echo "Routing index observation:"
query_table "WITH expected(label, pattern) AS (
  VALUES
    ('geometry GiST', '%USING gist (geometry%'),
    ('u/source node btree', '%(u)%'),
    ('v/target node btree', '%(v)%'),
    ('osmid btree', '%(osmid)%'),
    ('source column btree', '%(source)%'),
    ('target column btree', '%(target)%')
)
SELECT
  label,
  EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = 'public'
      AND tablename = 'moscow_network'
      AND lower(indexdef) LIKE lower(pattern)
  ) AS indexed
FROM expected
ORDER BY label;"

echo
echo "Required graph assets passed."
echo
echo "Current scoring-column coverage:"
query_table "SELECT
  count(*) AS edges,
  count(*) FILTER (WHERE safety_weight IS NOT NULL) AS safety_weight_count,
  count(*) FILTER (WHERE width IS NOT NULL) AS width_count,
  count(*) FILTER (WHERE est_width IS NOT NULL) AS est_width_count,
  count(*) FILTER (WHERE maxspeed IS NOT NULL) AS maxspeed_count,
  count(*) FILTER (WHERE lanes IS NOT NULL) AS lanes_count,
  count(*) FILTER (WHERE access IS NOT NULL) AS access_count
FROM public.moscow_network;"

echo
echo "Safety-weight distribution:"
query_table "SELECT
  min(safety_weight) AS min,
  percentile_cont(0.5) WITHIN GROUP (ORDER BY safety_weight) AS median,
  max(safety_weight) AS max,
  round(avg(safety_weight)::numeric, 3) AS avg
FROM public.moscow_network;"

echo
echo "Top highway values:"
query_table "SELECT lower(coalesce(highway, '')) AS highway, count(*)
FROM public.moscow_network
GROUP BY 1
ORDER BY count(*) DESC
LIMIT 15;"

echo
echo "Optional future enrichment columns present:"
query_table "SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema='public'
  AND table_name='moscow_network'
  AND column_name IN (
    'surface_type','surface','surface_quality','sidewalk_presence','sidewalk_width_m','sidewalk_width',
    'curb_frequency','curb_risk','crossing_count','lighting_quality','slope_percent','incline',
    'traffic_intensity','pedestrian_density','micromobility_allowed','forbidden_zone',
    'weather_sensitive_risk','telemetry_confidence'
  )
ORDER BY column_name;"

echo "Graph data check passed."
