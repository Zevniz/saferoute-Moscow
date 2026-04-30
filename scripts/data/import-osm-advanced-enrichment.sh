#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATABASE_URL="${DATABASE_URL:-postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db}"
OSM_EXTRACT_FILE="${OSM_EXTRACT_FILE:-data/osm/moscow-oblast.osm.pbf}"
OSM_ADVANCED_FACTORS="${OSM_ADVANCED_FACTORS:-curb,crossings}"
PYTHON_BIN="${PYTHON_BIN:-./venv/bin/python}"
OSMIUM_BIN="${OSMIUM_BIN:-osmium}"
SOURCE_URL="${SOURCE_URL:-https://download.geofabrik.de/russia/central-fed-district.html}"
ACTIVATE_ENRICHMENT="${ACTIVATE_ENRICHMENT:-true}"
ENRICHMENT_OUTPUT_DIR="${ENRICHMENT_OUTPUT_DIR:-data/enrichment/osm}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="${PYTHON_BIN_FALLBACK:-python3}"
fi

cd "$ROOT_DIR"

if [[ ! -f "$OSM_EXTRACT_FILE" ]]; then
  echo "fail: OSM extract does not exist: $OSM_EXTRACT_FILE" >&2
  exit 1
fi

if ! command -v "$OSMIUM_BIN" >/dev/null 2>&1; then
  echo "fail: osmium is required for real OSM advanced enrichment extraction" >&2
  exit 1
fi

IFS="," read -r -a requested_factors <<<"$OSM_ADVANCED_FACTORS"
for raw_factor in "${requested_factors[@]}"; do
  factor="$(printf "%s" "$raw_factor" | xargs)"
  if [[ -z "$factor" ]]; then
    continue
  fi
  case "$factor" in
    curb)
      min_matches="${OSM_CURB_MIN_MATCHES:-1000}"
      mapping_mode="${OSM_CURB_MAPPING_MODE:-curb-hybrid}"
      ;;
    crossings)
      min_matches="${OSM_CROSSINGS_MIN_MATCHES:-5000}"
      mapping_mode="${OSM_CROSSINGS_MAPPING_MODE:-direct-ways}"
      ;;
    *)
      echo "fail: unsupported OSM_ADVANCED_FACTORS entry: $factor" >&2
      exit 1
      ;;
  esac

  output_csv="$ENRICHMENT_OUTPUT_DIR/moscow-oblast-osm-$factor.csv"
  metadata_json="$ENRICHMENT_OUTPUT_DIR/moscow-oblast-osm-$factor.metadata.json"
  echo "Building real OSM $factor enrichment from $OSM_EXTRACT_FILE"
  "$PYTHON_BIN" scripts/data/build-osm-advanced-enrichment-csv.py \
    --database-url "$DATABASE_URL" \
    --osm-extract "$OSM_EXTRACT_FILE" \
    --factor "$factor" \
    --output "$output_csv" \
    --metadata-output "$metadata_json" \
    --source-url "$SOURCE_URL" \
    --osmium-bin "$OSMIUM_BIN" \
    --min-matches "$min_matches" \
    --mapping-mode "$mapping_mode"

  validation_passed="$("$PYTHON_BIN" - "$metadata_json" <<'PY'
from __future__ import annotations

import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    metadata = json.load(handle)
print("true" if metadata.get("validation", {}).get("passed") is True else "false")
PY
)"
  if [[ "$validation_passed" != "true" ]]; then
    echo "warn: OSM $factor validation did not pass; not importing as active enrichment." >&2
    continue
  fi

  dataset_version="$("$PYTHON_BIN" - "$metadata_json" <<'PY'
from __future__ import annotations

import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    metadata = json.load(handle)
print(metadata["dataset_version"])
PY
)"
  source_name="$("$PYTHON_BIN" - "$metadata_json" <<'PY'
from __future__ import annotations

import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    metadata = json.load(handle)
print(metadata["source_name"])
PY
)"
  source_checksum="$("$PYTHON_BIN" - "$metadata_json" <<'PY'
from __future__ import annotations

import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    metadata = json.load(handle)
print(metadata["generated_csv_sha256"])
PY
)"

  echo "Importing validated OSM $factor enrichment as dataset $dataset_version"
  DATABASE_URL="$DATABASE_URL" \
    ENRICHMENT_FILE="$output_csv" \
    DATASET_VERSION="$dataset_version" \
    SOURCE_NAME="$source_name" \
    SOURCE_URL="$SOURCE_URL" \
    SOURCE_CHECKSUM="$source_checksum" \
    SOURCE_METADATA_FILE="$metadata_json" \
    ACTIVATE_ENRICHMENT="$ACTIVATE_ENRICHMENT" \
    bash scripts/data/import-enrichment.sh
done

DATABASE_URL="$DATABASE_URL" bash scripts/report-enrichment.sh
