#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GRAPH_DUMP_FILE="${SAFEROUTE_GRAPH_DUMP_PATH:-${GRAPH_DUMP_FILE:-$ROOT_DIR/data/graph/moscow_network.dump}}"
PG_RESTORE_BIN="${PG_RESTORE_BIN:-pg_restore}"
JQ_BIN="${JQ_BIN:-jq}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "$1 is not available. Install PostgreSQL client tools / jq or set the matching *_BIN env." >&2
    exit 1
  fi
}

checksum_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

cd "$ROOT_DIR"
require_cmd "$PG_RESTORE_BIN"
require_cmd "$JQ_BIN"

if [[ ! -f "$GRAPH_DUMP_FILE" ]]; then
  echo "GRAPH_BOOTSTRAP_REQUIRED: graph dump is missing: ${GRAPH_DUMP_FILE#$ROOT_DIR/}" >&2
  echo "Create it from a real graph source with DATABASE_URL=... npm run db:graph-export." >&2
  exit 1
fi

if ! "$PG_RESTORE_BIN" --list "$GRAPH_DUMP_FILE" | awk '/TABLE/ && /public[[:space:]]+moscow_network/ { found = 1 } END { exit found ? 0 : 1 }'; then
  echo "fail: graph dump does not contain table public.moscow_network: ${GRAPH_DUMP_FILE#$ROOT_DIR/}" >&2
  exit 1
fi

manifest="${GRAPH_DUMP_FILE}.manifest.json"
if [[ ! -f "$manifest" ]]; then
  echo "fail: graph dump manifest is missing: ${manifest#$ROOT_DIR/}" >&2
  echo "The manifest must include dataset metadata, row counts, SRID, route version, and sha256 provenance." >&2
  exit 1
fi

dataset_table="$("$JQ_BIN" -r '.dataset_table // .dataset // empty' "$manifest")"
dataset_name="$("$JQ_BIN" -r '.dataset_name // empty' "$manifest")"
city="$("$JQ_BIN" -r '.city // empty' "$manifest")"
region="$("$JQ_BIN" -r '.region // empty' "$manifest")"
source_description="$("$JQ_BIN" -r '.source_description // empty' "$manifest")"
row_count="$("$JQ_BIN" -r '.row_count // 0' "$manifest")"
node_row_count="$("$JQ_BIN" -r '.node_row_count // empty' "$manifest")"
srid="$("$JQ_BIN" -r '.srid // empty' "$manifest")"
graph_schema_version="$("$JQ_BIN" -r '.graph_schema_version // empty' "$manifest")"
route_data_version="$("$JQ_BIN" -r '.route_data_version // empty' "$manifest")"
expected_sha="$("$JQ_BIN" -r '.sha256 // empty' "$manifest")"
actual_sha="$(checksum_file "$GRAPH_DUMP_FILE")"

if [[ "$dataset_table" != "public.moscow_network" ]]; then
  echo "fail: graph dump manifest dataset_table is '$dataset_table', expected public.moscow_network" >&2
  exit 1
fi

for required_value in dataset_name city region source_description graph_schema_version route_data_version; do
  if [[ -z "${!required_value}" ]]; then
    echo "fail: graph dump manifest is missing required field: $required_value" >&2
    exit 1
  fi
done

if [[ "$city" != "Moscow" ]]; then
  echo "fail: graph dump manifest city is '$city', expected Moscow" >&2
  exit 1
fi

if ! [[ "$row_count" =~ ^[0-9]+$ ]] || [[ "$row_count" -lt 1 ]]; then
  echo "fail: graph dump manifest row_count must be a positive integer" >&2
  exit 1
fi

if ! [[ "$node_row_count" =~ ^[0-9]+$ ]] || [[ "$node_row_count" -lt 1 ]]; then
  echo "fail: graph dump manifest node_row_count must be a positive integer" >&2
  exit 1
fi

if [[ "$srid" != "4326" ]]; then
  echo "fail: graph dump manifest SRID is '$srid', expected 4326" >&2
  exit 1
fi

if [[ -z "$expected_sha" || "$actual_sha" != "$expected_sha" ]]; then
  echo "fail: graph dump checksum mismatch" >&2
  echo "  expected: ${expected_sha:-missing}" >&2
  echo "  actual:   $actual_sha" >&2
  exit 1
fi

echo "Graph dump check passed."
echo "  dump: ${GRAPH_DUMP_FILE#$ROOT_DIR/}"
echo "  manifest: ${manifest#$ROOT_DIR/}"
echo "  dataset_name: $dataset_name"
echo "  dataset_table: $dataset_table"
echo "  city: $city"
echo "  region: $region"
echo "  row_count: $row_count"
echo "  node_row_count: $node_row_count"
echo "  srid: $srid"
echo "  graph_schema_version: $graph_schema_version"
echo "  route_data_version: $route_data_version"
echo "  sha256: $actual_sha"
