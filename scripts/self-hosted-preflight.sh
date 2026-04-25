#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.yml}"
API_URL="${API_URL:-http://127.0.0.1:8000}"
OSM_EXTRACT_FILE="${OSM_EXTRACT_FILE:-$ROOT_DIR/data/osm/moscow-oblast.osm.pbf}"
OSM_SOURCE_FILE="${OSM_SOURCE_FILE:-$ROOT_DIR/data/osm/central-fed-district-latest.osm.pbf}"
SOURCE_DATABASE_URL="${SOURCE_DATABASE_URL:-postgresql://artem@localhost:5433/artem}"
TARGET_DATABASE_URL="${TARGET_DATABASE_URL:-postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db}"
PSQL_BIN="${PSQL_BIN:-psql}"
PG_DUMP_BIN="${PG_DUMP_BIN:-pg_dump}"
REQUIRE_SOURCE_DB="${SELF_HOSTED_PREFLIGHT_REQUIRE_SOURCE_DB:-true}"

failures=0
warnings=0

redact_url() {
  printf "%s" "$1" | sed -E 's#(postgres(ql)?://[^:/@]+:)[^@]+@#\1***@#'
}

ok() {
  printf "ok: %s\n" "$1"
}

warn() {
  warnings=$((warnings + 1))
  printf "warn: %s\n" "$1" >&2
}

fail() {
  failures=$((failures + 1))
  printf "fail: %s\n" "$1" >&2
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

check_cmd() {
  local command_name="$1"
  local install_hint="$2"
  if have_cmd "$command_name"; then
    ok "$command_name is available at $(command -v "$command_name")"
    return 0
  fi
  fail "$command_name is missing. $install_hint"
  return 1
}

check_port() {
  local port="$1"
  local name="$2"
  if ! have_cmd lsof; then
    warn "lsof is not available; cannot check whether port $port ($name) is already in use."
    return
  fi
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    warn "port $port ($name) is already listening. This is OK if the self-hosted stack is already running; otherwise stop the conflicting process."
  else
    ok "port $port ($name) is free"
  fi
}

check_db_table_count() {
  local database_url="$1"
  local query="$2"
  local output
  if ! output="$(PGCONNECT_TIMEOUT=3 "$PSQL_BIN" "$database_url" -Atqc "$query" 2>/dev/null)"; then
    return 1
  fi
  printf "%s" "$output"
}

check_source_graph() {
  local count
  if ! count="$(check_db_table_count "$SOURCE_DATABASE_URL" "SELECT count(*) FROM public.moscow_network;")"; then
    return 1
  fi
  if [[ ! "$count" =~ ^[0-9]+$ || "$count" -le 0 ]]; then
    return 1
  fi
  ok "source DB has public.moscow_network with $count rows ($(redact_url "$SOURCE_DATABASE_URL"))"
  return 0
}

check_target_graph() {
  local count
  if ! count="$(check_db_table_count "$TARGET_DATABASE_URL" "SELECT count(*) FROM public.moscow_network;")"; then
    return 1
  fi
  if [[ ! "$count" =~ ^[0-9]+$ || "$count" -le 0 ]]; then
    return 1
  fi

  ok "compose DB already has public.moscow_network with $count rows ($(redact_url "$TARGET_DATABASE_URL"))"

  local extensions
  extensions="$(check_db_table_count "$TARGET_DATABASE_URL" "SELECT count(*) FROM pg_extension WHERE extname IN ('postgis','pgrouting');" || true)"
  if [[ "$extensions" == "2" ]]; then
    ok "compose DB has PostGIS and pgRouting extensions"
  else
    fail "compose DB is missing PostGIS and/or pgRouting extensions; recreate the compose DB volume or apply docker/postgres/init/01_extensions.sql to a real PostGIS database."
  fi

  local prepared_columns
  prepared_columns="$(check_db_table_count "$TARGET_DATABASE_URL" "SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='moscow_network' AND column_name IN ('cost_walk_safe','cost_bike_safe','cost_car_safe','source_x','source_y','target_x','target_y');" || true)"
  if [[ "$prepared_columns" == "7" ]]; then
    ok "compose DB has prepared routing columns"
  else
    warn "compose DB has moscow_network but does not expose all prepared routing columns; run scripts/prepare-production-db.sql or npm run bootstrap:self-hosted."
  fi

  local nodes_count
  nodes_count="$(check_db_table_count "$TARGET_DATABASE_URL" "SELECT count(*) FROM public.moscow_network_nodes;" || true)"
  if [[ "$nodes_count" =~ ^[0-9]+$ && "$nodes_count" -gt 0 ]]; then
    ok "compose DB has public.moscow_network_nodes with $nodes_count rows"
  else
    warn "compose DB does not expose a populated public.moscow_network_nodes relation; run scripts/prepare-production-db.sql or npm run bootstrap:self-hosted to restore prepared routing metadata."
  fi

  return 0
}

cd "$ROOT_DIR"

echo "SafeRoute self-hosted preflight"
echo "Root: $ROOT_DIR"
echo "API_URL=$API_URL"
echo "OSM_EXTRACT_FILE=${OSM_EXTRACT_FILE#$ROOT_DIR/}"
echo "SOURCE_DATABASE_URL=$(redact_url "$SOURCE_DATABASE_URL")"
echo "TARGET_DATABASE_URL=$(redact_url "$TARGET_DATABASE_URL")"
echo "ALLOW_PUBLIC_SERVICE_FALLBACK=${ALLOW_PUBLIC_SERVICE_FALLBACK:-false}"
echo

check_cmd docker "Install Docker Desktop or Docker Engine." || true
check_cmd node "Install Node.js for npm scripts." || true
check_cmd npm "Install npm for project scripts." || true
if have_cmd docker; then
  if docker info >/dev/null 2>&1; then
    ok "Docker daemon is running"
  else
    fail "Docker CLI is installed, but the Docker daemon is not responding. Start Docker Desktop or your Docker service, then rerun npm run self-hosted:preflight."
  fi

  if docker compose version >/dev/null 2>&1; then
    ok "docker compose is available ($(docker compose version --short 2>/dev/null || docker compose version))"
  else
    fail "docker compose is not available from the Docker CLI."
  fi
fi

if [[ -f "$COMPOSE_FILE" ]]; then
  ok "compose file found: $COMPOSE_FILE"
  if have_cmd docker && docker compose -f "$COMPOSE_FILE" config >/dev/null 2>&1; then
    ok "docker compose config is valid"
  else
    fail "docker compose config failed. Run docker compose config for details."
  fi
else
  fail "compose file is missing: $COMPOSE_FILE"
fi

for required_file in \
  "$ROOT_DIR/docker/postgres/init/01_extensions.sql" \
  "$ROOT_DIR/docker/postgres/init/02_telemetry.sql" \
  "$ROOT_DIR/scripts/prepare-production-db.sql"; do
  if [[ -f "$required_file" ]]; then
    ok "required schema/init file exists: ${required_file#$ROOT_DIR/}"
  else
    fail "required schema/init file is missing: ${required_file#$ROOT_DIR/}"
  fi
done

if [[ -f "$OSM_EXTRACT_FILE" ]]; then
  ok "Valhalla OSM extract exists: ${OSM_EXTRACT_FILE#$ROOT_DIR/}"
else
  fail "Valhalla OSM extract is missing: ${OSM_EXTRACT_FILE#$ROOT_DIR/}. Run npm run bootstrap:self-hosted, or run scripts/data/download-osm.sh and scripts/data/extract-moscow-oblast.sh."
  if [[ -f "$OSM_SOURCE_FILE" ]]; then
    ok "OSM source PBF exists and can be extracted: ${OSM_SOURCE_FILE#$ROOT_DIR/}"
  else
    warn "OSM source PBF is also missing; bootstrap will download it with curl."
  fi
fi

check_cmd curl "Install curl; it is used by startup and smoke checks." || true
if [[ -f "$OSM_EXTRACT_FILE" ]]; then
  if have_cmd osmium; then
    ok "osmium is available for rebuilding the OSM extract"
  else
    warn "osmium is missing. Existing extract can be used, but rebuilding data requires: brew install osmium-tool"
  fi
else
  check_cmd osmium "Install with: brew install osmium-tool" || true
fi

check_cmd "$PSQL_BIN" "Install PostgreSQL client tools or set PSQL_BIN." || true
check_cmd "$PG_DUMP_BIN" "Install PostgreSQL client tools or set PG_DUMP_BIN." || true

if have_cmd "$PSQL_BIN"; then
  if check_source_graph; then
    :
  elif check_target_graph; then
    warn "source DB is unavailable, but compose DB already has moscow_network. Full bootstrap imports from SOURCE_DATABASE_URL, so set it before rebuilding data."
  elif [[ "$REQUIRE_SOURCE_DB" == "true" ]]; then
    fail "public.moscow_network is not reachable in SOURCE_DATABASE_URL ($(redact_url "$SOURCE_DATABASE_URL")) and the compose DB does not already expose it. Full route verification needs real graph data; this script will not create fake data."
  else
    warn "source graph check skipped by SELF_HOSTED_PREFLIGHT_REQUIRE_SOURCE_DB=false. Smoke:self-hosted can still fail if compose PostGIS lacks public.moscow_network."
  fi
fi

check_port 5173 "frontend"
check_port 8000 "api"
check_port 5434 "compose postgres"
check_port 2322 "photon"
check_port 8002 "valhalla"

if have_cmd curl; then
  if response="$(curl -fsS --max-time 3 "$API_URL/api/health?deep=false" 2>/dev/null)"; then
    ok "API health endpoint responds at $API_URL/api/health?deep=false"
    printf "%s\n" "$response" | sed 's/^/  /'
  else
    warn "API health is not reachable at $API_URL. Start the stack with npm run self-hosted:up or npm run bootstrap:self-hosted before smoke tests."
  fi
fi

echo
echo "Preflight summary: $failures failure(s), $warnings warning(s)"
if [[ "$failures" -gt 0 ]]; then
  echo
  echo "Fix the failures above before expecting npm run smoke:self-hosted to pass." >&2
  exit 1
fi

echo "Self-hosted prerequisites look usable. Run npm run self-hosted:up, or npm run bootstrap:self-hosted when the routing graph must be imported/rebuilt."
