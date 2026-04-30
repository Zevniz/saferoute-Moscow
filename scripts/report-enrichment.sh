#!/usr/bin/env bash
set -euo pipefail

PSQL_BIN="${PSQL_BIN:-psql}"
DATABASE_URL="${DATABASE_URL:-postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db}"

redact_url() {
  sed -E 's#(postgres(ql)?://[^:/@]+):[^@]*@#\1:***@#' <<<"$1"
}

echo "SafeRoute enrichment report for $(redact_url "$DATABASE_URL")"
"$PSQL_BIN" "$DATABASE_URL" -P pager=off -c "
SELECT
  dataset_version,
  source_name,
  source_url,
  source_checksum,
  imported_at,
  is_active,
  metadata->>'license' AS license,
  metadata->>'mapping_method' AS mapping_method
FROM public.safety_enrichment_datasets
ORDER BY is_active DESC, imported_at DESC;
"

"$PSQL_BIN" "$DATABASE_URL" -P pager=off -c "
SELECT
  e.dataset_version,
  count(*) AS rows,
  count(*) FILTER (WHERE surface_type IS NOT NULL) AS surface_type,
  count(*) FILTER (WHERE surface_quality IS NOT NULL) AS surface_quality,
  count(*) FILTER (WHERE sidewalk_presence IS NOT NULL) AS sidewalk_presence,
  count(*) FILTER (WHERE lighting_quality IS NOT NULL) AS lighting_quality,
  count(*) FILTER (WHERE slope_percent IS NOT NULL) AS slope_percent,
  count(*) FILTER (WHERE curb_risk IS NOT NULL) AS curb_risk,
  count(*) FILTER (WHERE curb_density_per_km IS NOT NULL) AS curb_density_per_km,
  count(*) FILTER (WHERE crossing_count IS NOT NULL) AS crossing_count,
  count(*) FILTER (WHERE controlled_crossing_count IS NOT NULL) AS controlled_crossings,
  count(*) FILTER (WHERE uncontrolled_crossing_count IS NOT NULL) AS uncontrolled_crossings,
  count(*) FILTER (WHERE crossing_risk IS NOT NULL) AS crossing_risk,
  count(*) FILTER (WHERE traffic_intensity IS NOT NULL) AS traffic_intensity,
  count(*) FILTER (WHERE pedestrian_density IS NOT NULL) AS pedestrian_density,
  count(*) FILTER (WHERE micromobility_allowed IS NOT NULL OR forbidden_zone IS NOT NULL OR micromobility_slow_zone IS NOT NULL) AS micromobility_zones,
  count(*) FILTER (WHERE road_exposure_proxy IS NOT NULL) AS road_exposure_proxy,
  count(*) FILTER (WHERE weather_sensitive_risk IS NOT NULL) AS weather_sensitive_risk,
  count(*) FILTER (WHERE telemetry_confidence IS NOT NULL) AS telemetry_confidence,
  round(avg(confidence)::numeric, 3) AS avg_confidence
FROM public.safety_edge_enrichment e
JOIN public.safety_enrichment_datasets d USING (dataset_version)
GROUP BY e.dataset_version
ORDER BY bool_or(d.is_active) DESC, rows DESC;
"
