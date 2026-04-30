#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OSM_EXTRACT_FILE="${OSM_EXTRACT_FILE:-$ROOT_DIR/data/osm/moscow-oblast.osm.pbf}"
SOURCE_DATABASE_URL="${SOURCE_DATABASE_URL:-postgresql://artem@localhost:5433/artem}"
API_URL="${API_URL:-http://127.0.0.1:8000}"

cd "$ROOT_DIR"

redact_url() {
  sed -E 's#(postgres(ql)?://[^:/@]+):[^@]*@#\1:***@#' <<<"$1"
}

if [[ ! -f "$OSM_EXTRACT_FILE" ]]; then
  bash scripts/data/download-osm.sh
  bash scripts/data/extract-moscow-oblast.sh
fi

export ALLOW_PUBLIC_SERVICE_FALLBACK=false
export VALHALLA_TILE_URLS="${VALHALLA_TILE_URLS:-file:///custom_files/osm/moscow-oblast.osm.pbf}"
export ROUTE_DATA_VERSION="${ROUTE_DATA_VERSION:-moscow-oblast-$(stat -f %m "$OSM_EXTRACT_FILE" 2>/dev/null || stat -c %Y "$OSM_EXTRACT_FILE")}"

for port in 5173 8000; do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is already in use. Stop the conflicting local dev process before starting the self-hosted stack." >&2
    exit 1
  fi
done

echo "Starting self-hosted SafeRoute stack with fallback disabled."
echo "  OSM extract: $OSM_EXTRACT_FILE"
echo "  Valhalla tile source: $VALHALLA_TILE_URLS"
echo "  Route data version: $ROUTE_DATA_VERSION"
echo "  Source safety graph DB: $(redact_url "$SOURCE_DATABASE_URL")"

bash scripts/data/import-safety-graph.sh
docker compose up -d photon valhalla api frontend

echo "Waiting for API health endpoint..."
for _ in $(seq 1 180); do
  if curl -fsS "$API_URL/api/health?deep=true" >/dev/null 2>&1; then
    break
  fi
  docker compose ps
  sleep 5
done

API_URL="$API_URL" bash scripts/smoke-self-hosted.sh
