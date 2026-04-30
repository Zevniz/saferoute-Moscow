#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA_DIR="${DATA_DIR:-$ROOT_DIR/data/osm}"
OSM_SOURCE_URL="${OSM_SOURCE_URL:-https://download.geofabrik.de/russia/central-fed-district-latest.osm.pbf}"
OSM_SOURCE_FILE="${OSM_SOURCE_FILE:-$DATA_DIR/central-fed-district-latest.osm.pbf}"
OSM_SOURCE_PART_FILE="${OSM_SOURCE_PART_FILE:-$OSM_SOURCE_FILE.part}"
CURL_RETRY="${CURL_RETRY:-5}"
CURL_RETRY_DELAY="${CURL_RETRY_DELAY:-10}"
CURL_CONNECT_TIMEOUT="${CURL_CONNECT_TIMEOUT:-30}"
CURL_SPEED_TIME="${CURL_SPEED_TIME:-120}"
CURL_SPEED_LIMIT="${CURL_SPEED_LIMIT:-50000}"

mkdir -p "$DATA_DIR"

echo "Downloading official OSM source:"
echo "  $OSM_SOURCE_URL"
echo "  -> $OSM_SOURCE_PART_FILE"

curl \
  --continue-at - \
  --fail \
  --location \
  --retry "$CURL_RETRY" \
  --retry-delay "$CURL_RETRY_DELAY" \
  --connect-timeout "$CURL_CONNECT_TIMEOUT" \
  --speed-time "$CURL_SPEED_TIME" \
  --speed-limit "$CURL_SPEED_LIMIT" \
  --output "$OSM_SOURCE_PART_FILE" \
  "$OSM_SOURCE_URL"

if [[ ! -s "$OSM_SOURCE_PART_FILE" ]]; then
  echo "Downloaded file is empty: $OSM_SOURCE_PART_FILE" >&2
  exit 1
fi

checksum_file="$OSM_SOURCE_PART_FILE.sha256"
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$OSM_SOURCE_PART_FILE" | tee "$checksum_file"
else
  shasum -a 256 "$OSM_SOURCE_PART_FILE" | tee "$checksum_file"
fi

mv "$OSM_SOURCE_PART_FILE" "$OSM_SOURCE_FILE"
mv "$checksum_file" "$OSM_SOURCE_FILE.sha256"

echo "OSM source ready: $OSM_SOURCE_FILE"
echo "Checksum: $OSM_SOURCE_FILE.sha256"
