#!/usr/bin/env bash
set -euo pipefail

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
  PGCONNECT_TIMEOUT=5 "$PSQL_BIN" "$DATABASE_URL" -Atqc "$1"
}

query_table() {
  PGCONNECT_TIMEOUT=5 "$PSQL_BIN" "$DATABASE_URL" -c "$1"
}

fail_check() {
  echo "fail: $1" >&2
  echo "" >&2
  echo "Enrichment schema check failed for $(redact_url "$DATABASE_URL")." >&2
  echo "Run npm run db:migrate before importing real enrichment data." >&2
  exit 1
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

echo "Checking SafeRoute enrichment schema in $(redact_url "$DATABASE_URL")"

require_count_at_least \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('safety_enrichment_datasets','safety_edge_enrichment');" \
  2 \
  "enrichment tables"

require_count_at_least \
  "SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='safety_edge_enrichment' AND column_name IN ('edge_id','dataset_version','source_name','confidence','surface_type','surface_quality','sidewalk_presence','sidewalk_width_m','curb_risk','curb_frequency','curb_density_per_km','crossing_count','controlled_crossing_count','uncontrolled_crossing_count','crossing_risk','lighting_quality','slope_percent','traffic_intensity','pedestrian_density','micromobility_allowed','forbidden_zone','micromobility_slow_zone','zone_speed_limit_kmh','road_exposure_proxy','weather_sensitive_risk','telemetry_confidence');" \
  26 \
  "safety_edge_enrichment expected columns"

require_count_at_least \
  "SELECT count(*) FROM pg_indexes WHERE schemaname='public' AND indexname IN ('safety_edge_enrichment_edge_idx','safety_edge_enrichment_dataset_idx','safety_enrichment_datasets_active_idx');" \
  3 \
  "enrichment indexes"

echo
echo "Active enrichment datasets:"
query_table "SELECT dataset_version, source_name, source_url, imported_at, is_active
FROM public.safety_enrichment_datasets
ORDER BY imported_at DESC
LIMIT 10;"

echo
echo "Enrichment row coverage:"
query_table "SELECT
  count(*) AS rows,
  count(*) FILTER (WHERE surface_type IS NOT NULL) AS surface_type_count,
  count(*) FILTER (WHERE surface_quality IS NOT NULL) AS surface_quality_count,
  count(*) FILTER (WHERE sidewalk_presence IS NOT NULL) AS sidewalk_presence_count,
  count(*) FILTER (WHERE slope_percent IS NOT NULL) AS slope_percent_count,
  count(*) FILTER (WHERE lighting_quality IS NOT NULL) AS lighting_quality_count,
  count(*) FILTER (WHERE curb_risk IS NOT NULL) AS curb_risk_count,
  count(*) FILTER (WHERE curb_density_per_km IS NOT NULL) AS curb_density_count,
  count(*) FILTER (WHERE crossing_count IS NOT NULL) AS crossing_count_count,
  count(*) FILTER (WHERE crossing_risk IS NOT NULL) AS crossing_risk_count,
  count(*) FILTER (WHERE traffic_intensity IS NOT NULL) AS traffic_intensity_count,
  count(*) FILTER (WHERE pedestrian_density IS NOT NULL) AS pedestrian_density_count,
  count(*) FILTER (WHERE micromobility_allowed IS NOT NULL OR forbidden_zone IS NOT NULL OR micromobility_slow_zone IS NOT NULL) AS micromobility_zone_count,
  count(*) FILTER (WHERE weather_sensitive_risk IS NOT NULL) AS weather_risk_count,
  count(*) FILTER (WHERE telemetry_confidence IS NOT NULL) AS telemetry_confidence_count
FROM public.safety_edge_enrichment;"

echo
echo "Active factor coverage by dataset:"
query_table "SELECT
  e.dataset_version,
  d.is_active,
  count(*) AS rows,
  count(*) FILTER (WHERE surface_type IS NOT NULL) AS surface_type,
  count(*) FILTER (WHERE curb_risk IS NOT NULL OR curb_density_per_km IS NOT NULL) AS curb,
  count(*) FILTER (WHERE crossing_count IS NOT NULL OR crossing_risk IS NOT NULL) AS crossings,
  count(*) FILTER (WHERE traffic_intensity IS NOT NULL) AS measured_traffic,
  count(*) FILTER (WHERE pedestrian_density IS NOT NULL) AS pedestrian_density,
  count(*) FILTER (WHERE micromobility_allowed IS NOT NULL OR forbidden_zone IS NOT NULL OR micromobility_slow_zone IS NOT NULL) AS micromobility,
  count(*) FILTER (WHERE weather_sensitive_risk IS NOT NULL) AS weather,
  count(*) FILTER (WHERE telemetry_confidence IS NOT NULL) AS telemetry_confidence
FROM public.safety_edge_enrichment e
JOIN public.safety_enrichment_datasets d USING (dataset_version)
GROUP BY e.dataset_version, d.is_active
ORDER BY d.is_active DESC, rows DESC;"

echo "Enrichment schema check passed."
