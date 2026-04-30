#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATABASE_URL="${DATABASE_URL:-postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db}"
MICROMOBILITY_ZONES_FILE="${MICROMOBILITY_ZONES_FILE:-}"
DATASET_VERSION="${DATASET_VERSION:-}"
SOURCE_NAME="${SOURCE_NAME:-}"
SOURCE_OWNER="${SOURCE_OWNER:-}"
SOURCE_URL="${SOURCE_URL:-}"
SOURCE_LICENSE="${SOURCE_LICENSE:-}"
SOURCE_CHECKSUM="${SOURCE_CHECKSUM:-}"
ACTIVATE_ENRICHMENT="${ACTIVATE_ENRICHMENT:-false}"
DEACTIVATE_OTHER_ENRICHMENT_DATASETS="${DEACTIVATE_OTHER_ENRICHMENT_DATASETS:-false}"
PSQL_BIN="${PSQL_BIN:-psql}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
OGR2OGR_BIN="${OGR2OGR_BIN:-ogr2ogr}"

activate_normalized="$(printf "%s" "$ACTIVATE_ENRICHMENT" | tr '[:upper:]' '[:lower:]')"
deactivate_others_normalized="$(printf "%s" "$DEACTIVATE_OTHER_ENRICHMENT_DATASETS" | tr '[:upper:]' '[:lower:]')"

fail() {
  echo "fail: $*" >&2
  exit 1
}

if [[ "$activate_normalized" != "true" && "$activate_normalized" != "false" ]]; then
  fail "ACTIVATE_ENRICHMENT must be true or false"
fi

if [[ "$deactivate_others_normalized" != "true" && "$deactivate_others_normalized" != "false" ]]; then
  fail "DEACTIVATE_OTHER_ENRICHMENT_DATASETS must be true or false"
fi

if [[ -z "$MICROMOBILITY_ZONES_FILE" ]]; then
  fail "MICROMOBILITY_ZONES_FILE is required and must point to a real official GeoJSON or GeoPackage source"
fi

if [[ ! -f "$MICROMOBILITY_ZONES_FILE" ]]; then
  fail "MICROMOBILITY_ZONES_FILE does not exist: $MICROMOBILITY_ZONES_FILE"
fi

for required_name in DATASET_VERSION SOURCE_NAME SOURCE_OWNER SOURCE_URL SOURCE_LICENSE SOURCE_CHECKSUM; do
  if [[ -z "${!required_name:-}" ]]; then
    fail "$required_name is required for micromobility zone imports"
  fi
done

source_realpath="$("$PYTHON_BIN" - "$MICROMOBILITY_ZONES_FILE" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve())
PY
)"
case "$source_realpath" in
  */tests/fixtures/*)
    if [[ "$activate_normalized" == "true" ]]; then
      fail "test fixtures under tests/fixtures cannot be activated as production micromobility data"
    fi
    ;;
esac

actual_checksum="$("$PYTHON_BIN" - "$MICROMOBILITY_ZONES_FILE" <<'PY'
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

digest = hashlib.sha256()
with Path(sys.argv[1]).open("rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
print(digest.hexdigest())
PY
)"
expected_checksum="$(printf "%s" "$SOURCE_CHECKSUM" | sed -E 's/^sha256://I' | tr '[:upper:]' '[:lower:]')"
if [[ "$actual_checksum" != "$expected_checksum" ]]; then
  fail "SOURCE_CHECKSUM mismatch: expected sha256:$expected_checksum, got sha256:$actual_checksum"
fi

if ! command -v "$PSQL_BIN" >/dev/null 2>&1; then
  fail "psql not found. Set PSQL_BIN or install PostgreSQL client tools."
fi

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/saferoute-micromobility-zones.XXXXXX")"
trap 'rm -rf "$tmp_dir"' EXIT
normalized_geojson="$MICROMOBILITY_ZONES_FILE"
case "${MICROMOBILITY_ZONES_FILE##*.}" in
  geojson|json)
    ;;
  gpkg)
    if ! command -v "$OGR2OGR_BIN" >/dev/null 2>&1; then
      fail "GeoPackage import requires ogr2ogr. Convert to GeoJSON or set OGR2OGR_BIN."
    fi
    normalized_geojson="$tmp_dir/source.geojson"
    "$OGR2OGR_BIN" -f GeoJSON "$normalized_geojson" "$MICROMOBILITY_ZONES_FILE"
    ;;
  *)
    fail "unsupported micromobility zone format. Use GeoJSON (.geojson/.json) or GeoPackage (.gpkg)."
    ;;
esac

normalized_csv="$tmp_dir/zones.csv"
validation_report="$tmp_dir/validation-report.json"
cd "$ROOT_DIR"
"$PYTHON_BIN" scripts/data/validate-micromobility-zones.py "$normalized_geojson" "$normalized_csv" "$validation_report" >/dev/null
validation_json="$("$PYTHON_BIN" - "$validation_report" <<'PY'
from __future__ import annotations

import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
PY
)"

DATABASE_URL="$DATABASE_URL" PSQL_BIN="$PSQL_BIN" bash scripts/check-enrichment-schema.sh >/dev/null

"$PSQL_BIN" "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -v dataset_version="$DATASET_VERSION" \
  -v source_name="$SOURCE_NAME" \
  -v source_owner="$SOURCE_OWNER" \
  -v source_url="$SOURCE_URL" \
  -v source_license="$SOURCE_LICENSE" \
  -v source_checksum="sha256:$actual_checksum" \
  -v validation_json="$validation_json" \
  -v activate="$activate_normalized" \
  -v deactivate_others="$deactivate_others_normalized" <<SQL
BEGIN;

INSERT INTO public.safety_enrichment_datasets (
  dataset_version, source_name, source_url, source_checksum, metadata, is_active
)
VALUES (
  :'dataset_version',
  :'source_name',
  :'source_url',
  :'source_checksum',
  '{}'::jsonb,
  false
)
ON CONFLICT (dataset_version) DO UPDATE SET
  source_name = EXCLUDED.source_name,
  source_url = EXCLUDED.source_url,
  source_checksum = EXCLUDED.source_checksum;

CREATE TEMP TABLE micromobility_zone_import (
  feature_id TEXT NOT NULL,
  zone_type TEXT NOT NULL,
  zone_speed_limit_kmh DOUBLE PRECISION,
  confidence DOUBLE PRECISION NOT NULL,
  geometry_type TEXT NOT NULL,
  geometry_json TEXT NOT NULL
) ON COMMIT DROP;

\copy micromobility_zone_import FROM '$normalized_csv' WITH (FORMAT csv, HEADER true)

CREATE TEMP TABLE micromobility_zone_geom AS
SELECT
  feature_id,
  zone_type,
  zone_speed_limit_kmh,
  confidence,
  ST_SetSRID(ST_GeomFromGeoJSON(geometry_json), 4326) AS geom
FROM micromobility_zone_import;

DO \$\$
DECLARE
  invalid_geometry_count INTEGER;
  empty_geometry_count INTEGER;
  scored_feature_count INTEGER;
BEGIN
  SELECT count(*) INTO invalid_geometry_count
  FROM micromobility_zone_geom
  WHERE NOT ST_IsValid(geom);

  IF invalid_geometry_count > 0 THEN
    RAISE EXCEPTION 'micromobility zone import contains % invalid geometries', invalid_geometry_count;
  END IF;

  SELECT count(*) INTO empty_geometry_count
  FROM micromobility_zone_geom
  WHERE ST_IsEmpty(geom);

  IF empty_geometry_count > 0 THEN
    RAISE EXCEPTION 'micromobility zone import contains % empty geometries', empty_geometry_count;
  END IF;

  SELECT count(*) INTO scored_feature_count
  FROM micromobility_zone_geom
  WHERE zone_type IN ('forbidden', 'slow');

  IF scored_feature_count = 0 THEN
    RAISE EXCEPTION 'micromobility zone import has no forbidden or slow zones that can affect SafeRoute scoring';
  END IF;
END \$\$;

CREATE TEMP TABLE micromobility_zone_edge_matches AS
SELECT
  edge.id AS edge_id,
  max(zone.confidence) AS confidence,
  bool_or(zone.zone_type = 'forbidden') AS has_forbidden_zone,
  bool_or(zone.zone_type = 'slow') AS has_slow_zone,
  min(zone.zone_speed_limit_kmh) FILTER (WHERE zone.zone_type = 'slow') AS min_zone_speed_limit_kmh,
  count(*) AS intersecting_zone_count
FROM micromobility_zone_geom zone
JOIN public.moscow_network edge
  ON zone.zone_type IN ('forbidden', 'slow')
 AND ST_Intersects(edge.geometry, zone.geom)
GROUP BY edge.id;

DO \$\$
DECLARE
  matched_edge_count INTEGER;
BEGIN
  SELECT count(*) INTO matched_edge_count
  FROM micromobility_zone_edge_matches;

  IF matched_edge_count = 0 THEN
    RAISE EXCEPTION 'micromobility zone import has zero intersections with public.moscow_network';
  END IF;
END \$\$;

DELETE FROM public.safety_edge_enrichment
WHERE dataset_version = :'dataset_version';

INSERT INTO public.safety_edge_enrichment (
  edge_id, dataset_version, source_name, confidence, observed_at,
  micromobility_allowed, forbidden_zone, micromobility_slow_zone, zone_speed_limit_kmh
)
SELECT
  edge_id,
  :'dataset_version',
  :'source_name',
  confidence,
  now(),
  CASE WHEN has_forbidden_zone THEN false ELSE NULL END,
  CASE WHEN has_forbidden_zone THEN true ELSE NULL END,
  CASE WHEN has_slow_zone THEN true ELSE NULL END,
  min_zone_speed_limit_kmh
FROM micromobility_zone_edge_matches;

WITH feature_stats AS (
  SELECT
    count(*) AS feature_count,
    count(*) FILTER (WHERE zone_type = 'forbidden') AS forbidden_feature_count,
    count(*) FILTER (WHERE zone_type = 'slow') AS slow_feature_count,
    count(*) FILTER (WHERE zone_type = 'preferred') AS preferred_feature_count,
    count(*) FILTER (WHERE zone_type = 'dedicated') AS dedicated_feature_count,
    round(avg(confidence)::numeric, 6) AS avg_source_confidence
  FROM micromobility_zone_geom
),
edge_stats AS (
  SELECT
    count(*) AS edge_row_count,
    count(*) FILTER (WHERE has_forbidden_zone) AS forbidden_edge_count,
    count(*) FILTER (WHERE has_slow_zone) AS slow_edge_count,
    round(avg(confidence)::numeric, 6) AS avg_edge_confidence,
    min(min_zone_speed_limit_kmh) AS min_zone_speed_limit_kmh
  FROM micromobility_zone_edge_matches
),
metadata AS (
  SELECT jsonb_build_object(
    'source_owner', :'source_owner',
    'source_url', :'source_url',
    'license', :'source_license',
    'source_checksum', :'source_checksum',
    'mapping_method', 'official_zone_polygon_intersection',
    'geometry_type', 'Polygon/MultiPolygon',
    'srid', 4326,
    'feature_count', feature_stats.feature_count,
    'edge_row_count', edge_stats.edge_row_count,
    'avg_confidence', edge_stats.avg_edge_confidence,
    'min_zone_speed_limit_kmh', edge_stats.min_zone_speed_limit_kmh,
    'zone_type_counts', jsonb_build_object(
      'forbidden', feature_stats.forbidden_feature_count,
      'slow', feature_stats.slow_feature_count,
      'preferred', feature_stats.preferred_feature_count,
      'dedicated', feature_stats.dedicated_feature_count
    ),
    'factor_counts', jsonb_build_object(
      'micromobility_allowed', edge_stats.forbidden_edge_count,
      'forbidden_zone', edge_stats.forbidden_edge_count,
      'micromobility_slow_zone', edge_stats.slow_edge_count,
      'zone_speed_limit_kmh', edge_stats.slow_edge_count
    ),
    'validation', :'validation_json'::jsonb,
    'activation_policy', 'active only when source is official/legal, checksum-verified, geometry-valid, and edge-mapped'
  ) AS payload
  FROM feature_stats, edge_stats
)
UPDATE public.safety_enrichment_datasets
SET
  metadata = metadata.payload,
  is_active = CASE
    WHEN dataset_version = :'dataset_version' THEN (:'activate')::boolean
    WHEN (:'activate')::boolean AND (:'deactivate_others')::boolean THEN false
    ELSE is_active
  END
FROM metadata
WHERE safety_enrichment_datasets.dataset_version = :'dataset_version';

COMMIT;
SQL

DATABASE_URL="$DATABASE_URL" PSQL_BIN="$PSQL_BIN" bash scripts/check-enrichment-schema.sh
echo "Micromobility zone import completed for dataset $DATASET_VERSION (active=$activate_normalized)."
