#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATABASE_URL="${DATABASE_URL:-postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db}"
ENRICHMENT_FILE="${ENRICHMENT_FILE:-}"
DATASET_VERSION="${DATASET_VERSION:-}"
SOURCE_NAME="${SOURCE_NAME:-}"
SOURCE_URL="${SOURCE_URL:-}"
SOURCE_CHECKSUM="${SOURCE_CHECKSUM:-}"
SOURCE_METADATA_FILE="${SOURCE_METADATA_FILE:-}"
ACTIVATE_ENRICHMENT="${ACTIVATE_ENRICHMENT:-false}"
DEACTIVATE_OTHER_ENRICHMENT_DATASETS="${DEACTIVATE_OTHER_ENRICHMENT_DATASETS:-false}"
PSQL_BIN="${PSQL_BIN:-psql}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
activate_normalized="$(printf "%s" "$ACTIVATE_ENRICHMENT" | tr '[:upper:]' '[:lower:]')"
deactivate_others_normalized="$(printf "%s" "$DEACTIVATE_OTHER_ENRICHMENT_DATASETS" | tr '[:upper:]' '[:lower:]')"

if [[ -z "$ENRICHMENT_FILE" || -z "$DATASET_VERSION" || -z "$SOURCE_NAME" ]]; then
  echo "Usage: ENRICHMENT_FILE=real.csv DATASET_VERSION=2026-04 SOURCE_NAME=osm npm run db:enrichment-import" >&2
  echo "The CSV must contain real edge-mapped data, including edge_id and confidence. No fake enrichment rows are generated." >&2
  exit 1
fi

if [[ "$activate_normalized" != "true" && "$activate_normalized" != "false" ]]; then
  echo "fail: ACTIVATE_ENRICHMENT must be true or false" >&2
  exit 1
fi

if [[ "$deactivate_others_normalized" != "true" && "$deactivate_others_normalized" != "false" ]]; then
  echo "fail: DEACTIVATE_OTHER_ENRICHMENT_DATASETS must be true or false" >&2
  exit 1
fi

if [[ "$activate_normalized" == "true" && -z "$SOURCE_CHECKSUM" ]]; then
  echo "fail: ACTIVATE_ENRICHMENT=true requires SOURCE_CHECKSUM provenance for the real source file." >&2
  exit 1
fi

if [[ ! -f "$ENRICHMENT_FILE" ]]; then
  echo "fail: enrichment file does not exist: $ENRICHMENT_FILE" >&2
  exit 1
fi

metadata_json="{}"
if [[ -n "$SOURCE_METADATA_FILE" ]]; then
  if [[ ! -f "$SOURCE_METADATA_FILE" ]]; then
    echo "fail: SOURCE_METADATA_FILE does not exist: $SOURCE_METADATA_FILE" >&2
    exit 1
  fi
  metadata_json="$("$PYTHON_BIN" - "$SOURCE_METADATA_FILE" <<'PY'
from __future__ import annotations

import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
PY
)"
fi

if ! command -v "$PSQL_BIN" >/dev/null 2>&1; then
  echo "psql not found. Set PSQL_BIN or install PostgreSQL client tools." >&2
  exit 1
fi

cd "$ROOT_DIR"
DATABASE_URL="$DATABASE_URL" PSQL_BIN="$PSQL_BIN" bash scripts/check-enrichment-schema.sh >/dev/null

tmp_csv="$(mktemp "${TMPDIR:-/tmp}/saferoute-enrichment.XXXXXX.csv")"
trap 'rm -f "$tmp_csv"' EXIT
"$PYTHON_BIN" scripts/data/validate-enrichment-csv.py "$ENRICHMENT_FILE" "$tmp_csv" >/dev/null

if [[ "$activate_normalized" == "true" ]]; then
  "$PYTHON_BIN" - "$tmp_csv" <<'PY'
from __future__ import annotations

import csv
import sys

factor_columns = {
    "surface_type",
    "surface_quality",
    "sidewalk_presence",
    "sidewalk_width_m",
    "curb_risk",
    "curb_frequency",
    "curb_density_per_km",
    "crossing_count",
    "controlled_crossing_count",
    "uncontrolled_crossing_count",
    "crossing_risk",
    "lighting_quality",
    "slope_percent",
    "traffic_intensity",
    "pedestrian_density",
    "micromobility_allowed",
    "forbidden_zone",
    "micromobility_slow_zone",
    "zone_speed_limit_kmh",
    "road_exposure_proxy",
    "weather_sensitive_risk",
    "telemetry_confidence",
}

with open(sys.argv[1], newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    for row in reader:
        if any((row.get(column) or "").strip() for column in factor_columns):
            raise SystemExit(0)

raise SystemExit("fail: ACTIVATE_ENRICHMENT=true requires at least one real factor column populated.")
PY
fi

"$PSQL_BIN" "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -v dataset_version="$DATASET_VERSION" \
  -v source_name="$SOURCE_NAME" \
  -v source_url="$SOURCE_URL" \
  -v source_checksum="$SOURCE_CHECKSUM" \
  -v metadata_json="$metadata_json" \
  -v activate="$activate_normalized" \
  -v deactivate_others="$deactivate_others_normalized" <<SQL
BEGIN;

INSERT INTO safety_enrichment_datasets (
  dataset_version, source_name, source_url, source_checksum, metadata, is_active
)
VALUES (
  :'dataset_version',
  :'source_name',
  NULLIF(:'source_url', ''),
  NULLIF(:'source_checksum', ''),
  :'metadata_json'::jsonb,
  false
)
ON CONFLICT (dataset_version) DO UPDATE SET
  source_name = EXCLUDED.source_name,
  source_url = EXCLUDED.source_url,
  source_checksum = EXCLUDED.source_checksum,
  metadata = EXCLUDED.metadata;

CREATE TEMP TABLE safety_edge_enrichment_import (
  edge_id BIGINT NOT NULL,
  confidence DOUBLE PRECISION NOT NULL,
  observed_at TIMESTAMPTZ,
  surface_type TEXT,
  surface_quality TEXT,
  sidewalk_presence BOOLEAN,
  sidewalk_width_m DOUBLE PRECISION,
  curb_risk DOUBLE PRECISION,
  curb_frequency DOUBLE PRECISION,
  curb_density_per_km DOUBLE PRECISION,
  crossing_count INTEGER,
  controlled_crossing_count INTEGER,
  uncontrolled_crossing_count INTEGER,
  crossing_risk DOUBLE PRECISION,
  lighting_quality TEXT,
  slope_percent DOUBLE PRECISION,
  traffic_intensity DOUBLE PRECISION,
  pedestrian_density DOUBLE PRECISION,
  micromobility_allowed BOOLEAN,
  forbidden_zone BOOLEAN,
  micromobility_slow_zone BOOLEAN,
  zone_speed_limit_kmh DOUBLE PRECISION,
  road_exposure_proxy DOUBLE PRECISION,
  weather_sensitive_risk DOUBLE PRECISION,
  telemetry_confidence DOUBLE PRECISION
) ON COMMIT DROP;

\copy safety_edge_enrichment_import FROM '$tmp_csv' WITH (FORMAT csv, HEADER true)

DO \$\$
DECLARE
  missing_edges INTEGER;
BEGIN
  SELECT count(*)
  INTO missing_edges
  FROM safety_edge_enrichment_import imported
  LEFT JOIN public.moscow_network edge
    ON edge.id = imported.edge_id
  WHERE edge.id IS NULL;

  IF missing_edges > 0 THEN
    RAISE EXCEPTION 'enrichment import references % missing public.moscow_network edge ids', missing_edges;
  END IF;
END \$\$;

INSERT INTO safety_edge_enrichment (
  edge_id, dataset_version, source_name, confidence, observed_at,
  surface_type, surface_quality, sidewalk_presence, sidewalk_width_m,
  curb_risk, curb_frequency, curb_density_per_km, crossing_count,
  controlled_crossing_count, uncontrolled_crossing_count, crossing_risk,
  lighting_quality, slope_percent, traffic_intensity, pedestrian_density,
  micromobility_allowed, forbidden_zone, micromobility_slow_zone,
  zone_speed_limit_kmh, road_exposure_proxy, weather_sensitive_risk,
  telemetry_confidence
)
SELECT
  edge_id, :'dataset_version', :'source_name', confidence, observed_at,
  surface_type, surface_quality, sidewalk_presence, sidewalk_width_m,
  curb_risk, curb_frequency, curb_density_per_km, crossing_count,
  controlled_crossing_count, uncontrolled_crossing_count, crossing_risk,
  lighting_quality, slope_percent, traffic_intensity, pedestrian_density,
  micromobility_allowed, forbidden_zone, micromobility_slow_zone,
  zone_speed_limit_kmh, road_exposure_proxy, weather_sensitive_risk,
  telemetry_confidence
FROM safety_edge_enrichment_import
ON CONFLICT (edge_id, dataset_version) DO UPDATE SET
  source_name = EXCLUDED.source_name,
  confidence = EXCLUDED.confidence,
  observed_at = EXCLUDED.observed_at,
  surface_type = EXCLUDED.surface_type,
  surface_quality = EXCLUDED.surface_quality,
  sidewalk_presence = EXCLUDED.sidewalk_presence,
  sidewalk_width_m = EXCLUDED.sidewalk_width_m,
  curb_risk = EXCLUDED.curb_risk,
  curb_frequency = EXCLUDED.curb_frequency,
  curb_density_per_km = EXCLUDED.curb_density_per_km,
  crossing_count = EXCLUDED.crossing_count,
  controlled_crossing_count = EXCLUDED.controlled_crossing_count,
  uncontrolled_crossing_count = EXCLUDED.uncontrolled_crossing_count,
  crossing_risk = EXCLUDED.crossing_risk,
  lighting_quality = EXCLUDED.lighting_quality,
  slope_percent = EXCLUDED.slope_percent,
  traffic_intensity = EXCLUDED.traffic_intensity,
  pedestrian_density = EXCLUDED.pedestrian_density,
  micromobility_allowed = EXCLUDED.micromobility_allowed,
  forbidden_zone = EXCLUDED.forbidden_zone,
  micromobility_slow_zone = EXCLUDED.micromobility_slow_zone,
  zone_speed_limit_kmh = EXCLUDED.zone_speed_limit_kmh,
  road_exposure_proxy = EXCLUDED.road_exposure_proxy,
  weather_sensitive_risk = EXCLUDED.weather_sensitive_risk,
  telemetry_confidence = EXCLUDED.telemetry_confidence;

UPDATE safety_enrichment_datasets
SET is_active = CASE
  WHEN dataset_version = :'dataset_version' THEN (:'activate')::boolean
  WHEN (:'activate')::boolean AND (:'deactivate_others')::boolean THEN false
  ELSE is_active
END;

COMMIT;
SQL

DATABASE_URL="$DATABASE_URL" PSQL_BIN="$PSQL_BIN" bash scripts/check-enrichment-schema.sh
echo "Enrichment import completed for dataset $DATASET_VERSION."
