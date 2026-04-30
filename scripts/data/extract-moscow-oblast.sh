#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA_DIR="${DATA_DIR:-$ROOT_DIR/data/osm}"
OSM_SOURCE_FILE="${OSM_SOURCE_FILE:-$DATA_DIR/central-fed-district-latest.osm.pbf}"
OSM_EXTRACT_FILE="${OSM_EXTRACT_FILE:-$DATA_DIR/moscow-oblast.osm.pbf}"
MOSCOW_OBLAST_BBOX="${MOSCOW_OBLAST_BBOX:-35.0,54.0,40.5,57.2}"

if ! command -v osmium >/dev/null 2>&1; then
  echo "osmium is required. Install with: brew install osmium-tool" >&2
  exit 1
fi

if [[ ! -f "$OSM_SOURCE_FILE" ]]; then
  echo "Missing source PBF: $OSM_SOURCE_FILE" >&2
  echo "Run scripts/data/download-osm.sh first." >&2
  exit 1
fi

mkdir -p "$DATA_DIR"

echo "Extracting Moscow+Oblast bbox $MOSCOW_OBLAST_BBOX"
echo "  $OSM_SOURCE_FILE"
echo "  -> $OSM_EXTRACT_FILE"

osmium extract \
  --bbox "$MOSCOW_OBLAST_BBOX" \
  --strategy smart \
  --overwrite \
  --output "$OSM_EXTRACT_FILE" \
  "$OSM_SOURCE_FILE"

echo "Moscow+Oblast extract ready: $OSM_EXTRACT_FILE"
