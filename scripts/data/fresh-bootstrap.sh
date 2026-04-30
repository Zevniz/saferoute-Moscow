#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FRESH_PROJECT_NAME="${FRESH_PROJECT_NAME:-saferoute-fresh-test}"
FRESH_API_PORT="${FRESH_API_PORT:-18000}"
FRESH_FRONTEND_PORT="${FRESH_FRONTEND_PORT:-15173}"
FRESH_DB_PORT="${FRESH_DB_PORT:-15434}"
FRESH_PHOTON_PORT="${FRESH_PHOTON_PORT:-12322}"
FRESH_VALHALLA_PORT="${FRESH_VALHALLA_PORT:-18002}"
FRESH_TEST_KEEP_STACK="${FRESH_TEST_KEEP_STACK:-false}"
GRAPH_DUMP_FILE="${SAFEROUTE_GRAPH_DUMP_PATH:-${GRAPH_DUMP_FILE:-$ROOT_DIR/data/graph/moscow_network.dump}}"
SOURCE_DATABASE_URL="${SOURCE_DATABASE_URL:-postgresql://artem@localhost:5433/artem}"
PSQL_BIN="${PSQL_BIN:-psql}"

cd "$ROOT_DIR"

cleanup() {
  if [[ "$FRESH_TEST_KEEP_STACK" != "true" && -n "${override_file:-}" && -f "$override_file" ]]; then
    docker compose -p "$FRESH_PROJECT_NAME" -f docker-compose.yml -f "$override_file" down -v >/dev/null 2>&1 || true
    rm -f "$override_file"
  fi
}
trap cleanup EXIT

check_port_free() {
  local port="$1"
  local label="$2"
  if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "fail: fresh bootstrap port $port ($label) is already in use. Override FRESH_*_PORT or stop the conflicting service." >&2
    exit 1
  fi
}

has_source_db=false
has_dump=false
if SOURCE_DATABASE_URL="$SOURCE_DATABASE_URL" PSQL_BIN="$PSQL_BIN" MIN_GRAPH_ROWS=1 bash scripts/check-graph-source.sh >/dev/null 2>&1; then
  has_source_db=true
fi
if GRAPH_DUMP_FILE="$GRAPH_DUMP_FILE" bash scripts/data/check-graph-dump.sh >/dev/null 2>&1; then
  has_dump=true
fi

if [[ "$has_source_db" != "true" && "$has_dump" != "true" ]]; then
  echo "GRAPH_BOOTSTRAP_REQUIRED: fresh bootstrap cannot run without a real graph source." >&2
  echo "Provide SOURCE_DATABASE_URL with public.moscow_network or GRAPH_DUMP_FILE=${GRAPH_DUMP_FILE#$ROOT_DIR/}." >&2
  echo "This script uses isolated Docker volumes and never creates fake graph data." >&2
  exit 1
fi

check_port_free "$FRESH_API_PORT" "api"
check_port_free "$FRESH_FRONTEND_PORT" "frontend"
check_port_free "$FRESH_DB_PORT" "postgres"
check_port_free "$FRESH_PHOTON_PORT" "photon"
check_port_free "$FRESH_VALHALLA_PORT" "valhalla"

override_file="$(mktemp "${TMPDIR:-/tmp}/saferoute-fresh-compose.XXXXXX")"
cat > "$override_file" <<YAML
services:
  frontend:
    image: saferoute-ultimate-frontend:latest
    build: !reset null
    ports: !override
      - "${FRESH_FRONTEND_PORT}:5173"
  api:
    image: saferoute-ultimate-api:latest
    build: !reset null
    ports: !override
      - "${FRESH_API_PORT}:8000"
  db:
    ports: !override
      - "${FRESH_DB_PORT}:5432"
  photon:
    ports: !override
      - "${FRESH_PHOTON_PORT}:2322"
  valhalla:
    ports: !override
      - "${FRESH_VALHALLA_PORT}:8002"
YAML

target_database_url="postgresql://saferoute:saferoute_pass@127.0.0.1:${FRESH_DB_PORT}/saferoute_db"

echo "Starting isolated fresh bootstrap project: $FRESH_PROJECT_NAME"
docker compose -p "$FRESH_PROJECT_NAME" -f docker-compose.yml -f "$override_file" down -v >/dev/null 2>&1 || true
docker compose -p "$FRESH_PROJECT_NAME" -f docker-compose.yml -f "$override_file" up -d db

if [[ "$has_dump" == "true" ]]; then
  TARGET_DATABASE_URL="$target_database_url" GRAPH_DUMP_FILE="$GRAPH_DUMP_FILE" FORCE_DB_IMPORT=true bash scripts/data/restore-safety-graph.sh
else
  COMPOSE_PROJECT_NAME="$FRESH_PROJECT_NAME" \
    COMPOSE_OVERRIDE_FILE="$override_file" \
    TARGET_DATABASE_URL="$target_database_url" \
    SOURCE_DATABASE_URL="$SOURCE_DATABASE_URL" \
    FORCE_DB_IMPORT=true \
    bash scripts/data/import-safety-graph.sh
fi

DATABASE_URL="$target_database_url" bash scripts/run-migrations.sh
DATABASE_URL="$target_database_url" bash scripts/check-enrichment-schema.sh
DATABASE_URL="$target_database_url" bash scripts/check-telemetry-schema.sh
DATABASE_URL="$target_database_url" bash scripts/check-graph-data.sh

docker compose -p "$FRESH_PROJECT_NAME" -f docker-compose.yml -f "$override_file" up -d photon valhalla api frontend

echo "Waiting for fresh API on http://127.0.0.1:${FRESH_API_PORT}"
for _ in $(seq 1 90); do
  if curl -fsS "http://127.0.0.1:${FRESH_API_PORT}/api/health?deep=false" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

API_URL="http://127.0.0.1:${FRESH_API_PORT}" npm run smoke:api
API_URL="http://127.0.0.1:${FRESH_API_PORT}" npm run smoke:self-hosted

if [[ "$FRESH_TEST_KEEP_STACK" == "true" ]]; then
  echo "Fresh stack left running by FRESH_TEST_KEEP_STACK=true"
  echo "Stop it with: docker compose -p $FRESH_PROJECT_NAME -f docker-compose.yml -f $override_file down -v"
else
  echo "Fresh bootstrap verification passed; isolated stack will be removed."
fi
