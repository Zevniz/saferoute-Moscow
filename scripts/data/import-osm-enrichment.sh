#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATABASE_URL="${DATABASE_URL:-postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db}"
OSM_EXTRACT_FILE="${OSM_EXTRACT_FILE:-$ROOT_DIR/data/osm/moscow-oblast.osm.pbf}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/data/enrichment/osm}"
OUTPUT_FILE="${OUTPUT_FILE:-$OUTPUT_DIR/moscow-oblast-osm-enrichment.csv}"
METADATA_FILE="${METADATA_FILE:-$OUTPUT_DIR/moscow-oblast-osm-enrichment.metadata.json}"
SOURCE_URL="${SOURCE_URL:-https://download.geofabrik.de/russia/central-fed-district.html}"
ACTIVATE_ENRICHMENT="${ACTIVATE_ENRICHMENT:-false}"
OSM_ENRICHMENT_FACTORS="${OSM_ENRICHMENT_FACTORS:-surface,sidewalk,lighting,slope}"
DATASET_VERSION="${DATASET_VERSION:-}"
PSQL_BIN="${PSQL_BIN:-psql}"
OSMIUM_BIN="${OSMIUM_BIN:-osmium}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

redact_url() {
  sed -E 's#(postgres(ql)?://[^:/@]+):[^@]*@#\1:***@#' <<<"$1"
}

if [[ ! -f "$OSM_EXTRACT_FILE" ]]; then
  echo "fail: OSM extract is missing: $OSM_EXTRACT_FILE" >&2
  echo "Run scripts/data/download-osm.sh and scripts/data/extract-moscow-oblast.sh first." >&2
  exit 1
fi

if ! command -v "$OSMIUM_BIN" >/dev/null 2>&1; then
  echo "fail: osmium is required for OSM enrichment import." >&2
  exit 1
fi

if ! command -v "$PSQL_BIN" >/dev/null 2>&1; then
  echo "fail: psql is required for OSM enrichment import." >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "Building real OSM edge enrichment CSV from $OSM_EXTRACT_FILE"
echo "  database: $(redact_url "$DATABASE_URL")"
"$PYTHON_BIN" "$ROOT_DIR/scripts/data/build-osm-enrichment-csv.py" \
  --database-url "$DATABASE_URL" \
  --osm-extract "$OSM_EXTRACT_FILE" \
  --output "$OUTPUT_FILE" \
  --metadata-output "$METADATA_FILE" \
  --dataset-version "$DATASET_VERSION" \
  --source-url "$SOURCE_URL" \
  --factors "$OSM_ENRICHMENT_FACTORS" \
  --psql-bin "$PSQL_BIN" \
  --osmium-bin "$OSMIUM_BIN" >/dev/null

resolved_dataset_version="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["dataset_version"])' "$METADATA_FILE")"
source_checksum="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["source_sha256"])' "$METADATA_FILE")"
import_rows="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["import_rows"])' "$METADATA_FILE")"

if [[ "$import_rows" == "0" ]]; then
  echo "fail: OSM enrichment extraction produced zero edge-mapped rows." >&2
  exit 1
fi

echo "Generated $import_rows edge-mapped OSM enrichment rows."
ENRICHMENT_FILE="$OUTPUT_FILE" \
DATASET_VERSION="$resolved_dataset_version" \
SOURCE_NAME="OpenStreetMap Moscow Oblast way tags" \
SOURCE_URL="$SOURCE_URL" \
SOURCE_CHECKSUM="$source_checksum" \
SOURCE_METADATA_FILE="$METADATA_FILE" \
ACTIVATE_ENRICHMENT="$ACTIVATE_ENRICHMENT" \
DATABASE_URL="$DATABASE_URL" \
PSQL_BIN="$PSQL_BIN" \
PYTHON_BIN="$PYTHON_BIN" \
bash "$ROOT_DIR/scripts/data/import-enrichment.sh"
