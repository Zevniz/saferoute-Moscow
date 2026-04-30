#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DATABASE_URL="${SOURCE_DATABASE_URL:-postgresql://artem@localhost:5433/artem}"
GRAPH_DUMP_FILE="${SAFEROUTE_GRAPH_DUMP_PATH:-${GRAPH_DUMP_FILE:-$ROOT_DIR/data/graph/moscow_network.dump}}"
PSQL_BIN="${PSQL_BIN:-psql}"

cd "$ROOT_DIR"

source_ok=false
dump_ok=false

if SOURCE_DATABASE_URL="$SOURCE_DATABASE_URL" PSQL_BIN="$PSQL_BIN" MIN_GRAPH_ROWS=1 bash scripts/check-graph-source.sh >/dev/null 2>&1; then
  source_ok=true
fi

if GRAPH_DUMP_FILE="$GRAPH_DUMP_FILE" bash scripts/data/check-graph-dump.sh >/dev/null 2>&1; then
  dump_ok=true
fi

if [[ "$source_ok" == "true" || "$dump_ok" == "true" ]]; then
  echo "Bootstrap source check passed."
  [[ "$source_ok" == "true" ]] && echo "ok: SOURCE_DATABASE_URL exposes a real public.moscow_network"
  [[ "$dump_ok" == "true" ]] && echo "ok: graph dump and manifest verify at ${GRAPH_DUMP_FILE#$ROOT_DIR/}"
  exit 0
fi

echo "GRAPH_BOOTSTRAP_REQUIRED: no reproducible graph source is available." >&2
echo "" >&2
echo "Provide one of:" >&2
echo "  SOURCE_DATABASE_URL=postgresql://... with real public.moscow_network" >&2
echo "  SAFEROUTE_GRAPH_DUMP_PATH=data/graph/moscow_network.dump from npm run db:graph-export" >&2
echo "" >&2
echo "This check never creates fake graph data." >&2
exit 1
