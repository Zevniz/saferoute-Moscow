#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export DATABASE_URL="${DATABASE_URL:-postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db}"
export OSM_EXTRACT_FILE="${OSM_EXTRACT_FILE:-$ROOT_DIR/data/osm/moscow-oblast.osm.pbf}"
export ACTIVATE_ENRICHMENT="${ACTIVATE_ENRICHMENT:-true}"
export DATASET_VERSION="${DATASET_VERSION:-moscow-oblast-v1}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "fail: Python is required. Install python3." >&2
  exit 1
fi
export PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v osmium >/dev/null 2>&1; then
  echo "fail: osmium is required. Install with: pip install osmium" >&2
  exit 1
fi

if [[ ! -f "$OSM_EXTRACT_FILE" ]]; then
  echo "fail: OSM extract not found: $OSM_EXTRACT_FILE" >&2
  echo "Download with: bash scripts/data/download-osm.sh" >&2
  exit 1
fi

mkdir -p "$ROOT_DIR/data/enrichment/osm"

echo "=== Step 1: Import basic OSM tags (surface, sidewalk, lighting, slope) ==="
bash "$ROOT_DIR/scripts/data/import-osm-enrichment.sh"

echo ""
echo "=== Step 2: Import advanced OSM factors (crossings, curb) ==="
bash "$ROOT_DIR/scripts/data/import-osm-advanced-enrichment.sh"

echo ""
echo "=== Enrichment import complete ==="
echo "Verifying:"
DATABASE_URL="$DATABASE_URL" PSQL_BIN="${PSQL_BIN:-psql}" bash "$ROOT_DIR/scripts/check-enrichment.sh"
