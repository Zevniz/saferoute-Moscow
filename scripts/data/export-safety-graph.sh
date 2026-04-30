#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATABASE_URL="${DATABASE_URL:-postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db}"
GRAPH_DUMP_FILE="${SAFEROUTE_GRAPH_DUMP_PATH:-${GRAPH_DUMP_FILE:-$ROOT_DIR/data/graph/moscow_network.dump}}"
GRAPH_DATASET_NAME="${GRAPH_DATASET_NAME:-SafeRoute Moscow safety graph}"
GRAPH_DATASET_TABLE="${GRAPH_DATASET_TABLE:-public.moscow_network}"
GRAPH_CITY="${GRAPH_CITY:-Moscow}"
GRAPH_REGION="${GRAPH_REGION:-Moscow and Moscow Oblast}"
GRAPH_SCHEMA_VERSION="${GRAPH_SCHEMA_VERSION:-1}"
ROUTE_DATA_VERSION="${ROUTE_DATA_VERSION:-moscow-network-v1}"
GRAPH_SOURCE_DESCRIPTION="${GRAPH_SOURCE_DESCRIPTION:-Exported from a real SafeRoute PostGIS public.moscow_network database}"
PSQL_BIN="${PSQL_BIN:-psql}"
PG_DUMP_BIN="${PG_DUMP_BIN:-pg_dump}"
JQ_BIN="${JQ_BIN:-jq}"

redact_url() {
  printf "%s" "$1" | sed -E 's#(postgres(ql)?://[^:/@]+:)[^@]+@#\1***@#'
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "$1 is not available. Install PostgreSQL client tools or set the matching *_BIN env." >&2
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

require_cmd "$PSQL_BIN"
require_cmd "$PG_DUMP_BIN"
require_cmd "$JQ_BIN"

cd "$ROOT_DIR"
DATABASE_URL="$DATABASE_URL" PSQL_BIN="$PSQL_BIN" bash scripts/check-graph-data.sh

mkdir -p "$(dirname "$GRAPH_DUMP_FILE")"
echo "Exporting real SafeRoute graph from $(redact_url "$DATABASE_URL") to ${GRAPH_DUMP_FILE#$ROOT_DIR/}"
"$PG_DUMP_BIN" "$DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-privileges \
  --table=public.moscow_network \
  --file="$GRAPH_DUMP_FILE"

row_count="$(PGCONNECT_TIMEOUT=5 "$PSQL_BIN" "$DATABASE_URL" -Atqc "SELECT count(*) FROM public.moscow_network;")"
node_row_count="$(
  PGCONNECT_TIMEOUT=5 "$PSQL_BIN" "$DATABASE_URL" -Atqc \
    "SELECT CASE WHEN to_regclass('public.moscow_network_nodes') IS NULL THEN 0 ELSE (SELECT count(*) FROM public.moscow_network_nodes) END;"
)"
srid="$(PGCONNECT_TIMEOUT=5 "$PSQL_BIN" "$DATABASE_URL" -Atqc "SELECT COALESCE((SELECT ST_SRID(geometry)::text FROM public.moscow_network WHERE geometry IS NOT NULL LIMIT 1), 'missing');")"
sha256="$(checksum_file "$GRAPH_DUMP_FILE")"
created_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
manifest="${GRAPH_DUMP_FILE}.manifest.json"

"$JQ_BIN" -n \
  --arg dataset_name "$GRAPH_DATASET_NAME" \
  --arg dataset_table "$GRAPH_DATASET_TABLE" \
  --arg city "$GRAPH_CITY" \
  --arg region "$GRAPH_REGION" \
  --arg created_at "$created_at" \
  --arg source_description "$GRAPH_SOURCE_DESCRIPTION" \
  --arg source_database_url_redacted "$(redact_url "$DATABASE_URL")" \
  --arg sha256 "$sha256" \
  --arg srid "$srid" \
  --arg graph_schema_version "$GRAPH_SCHEMA_VERSION" \
  --arg route_data_version "$ROUTE_DATA_VERSION" \
  --argjson row_count "$row_count" \
  --argjson node_row_count "$node_row_count" \
  '{
    dataset_name: $dataset_name,
    dataset_table: $dataset_table,
    city: $city,
    region: $region,
    created_at: $created_at,
    source_description: $source_description,
    source_database_url_redacted: $source_database_url_redacted,
    sha256: $sha256,
    row_count: $row_count,
    node_row_count: $node_row_count,
    srid: $srid,
    graph_schema_version: $graph_schema_version,
    route_data_version: $route_data_version
  }' > "$manifest"

echo "Graph dump exported."
echo "  dump: ${GRAPH_DUMP_FILE#$ROOT_DIR/}"
echo "  manifest: ${manifest#$ROOT_DIR/}"
echo "  sha256: $sha256"
