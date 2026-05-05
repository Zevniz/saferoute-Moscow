#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PSQL_BIN="${PSQL_BIN:-psql}"

if [[ -n "${DATABASE_URL:-}" ]]; then
  DB_URL="$DATABASE_URL"
else
  if docker compose ps db >/dev/null 2>&1; then
    DB_URL="postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db"
  else
    echo "Error: Docker compose stack not running and DATABASE_URL not set." >&2
    exit 1
  fi
fi

redact_url() { printf "%s" "$1" | sed -E 's#(postgres(ql)?://[^:/@]+:)[^@]+@#\1***@#'; }

echo "SafeRoute enrichment status:"
echo "  Database: $(redact_url "$DB_URL")"
echo ""

NETWORK_ROWS=$($PSQL_BIN "$DB_URL" -Atqc "SELECT COUNT(*) FROM public.moscow_network;" 2>/dev/null || echo 0)
echo "  Base graph (moscow_network): $NETWORK_ROWS rows"

if $PSQL_BIN "$DB_URL" -Atqc "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='safety_edge_enrichment'" >/dev/null 2>&1; then
  ENRICH_ROWS=$($PSQL_BIN "$DB_URL" -Atqc "SELECT COUNT(*) FROM public.safety_edge_enrichment;" 2>/dev/null || echo 0)
  echo "  Enrichment overlay (safety_edge_enrichment): $ENRICH_ROWS rows"
else
  echo "  Enrichment overlay: table missing (run enrichment:import)"
fi

ACTIVE_COUNT=$($PSQL_BIN "$DB_URL" -Atqc "SELECT COUNT(*) FROM public.safety_enrichment_datasets WHERE is_active = true;" 2>/dev/null || echo 0)
echo "  Active enrichment datasets: $ACTIVE_COUNT"

if [[ "$ACTIVE_COUNT" -gt 0 ]]; then
  $PSQL_BIN "$DB_URL" -P pager=off -c "
SELECT dataset_version, metadata->'avg_confidence' AS avg_conf, metadata->'active_factors' AS factors FROM public.safety_enrichment_datasets WHERE is_active = true ORDER BY imported_at DESC;"
fi

echo ""
echo "Summary:"
if [[ "$NETWORK_ROWS" -lt 1000 ]]; then
  echo "  FAIL: base graph missing or empty"
elif [[ "$ENRICH_ROWS" -eq 0 && "$ACTIVE_COUNT" -eq 0 ]]; then
  echo "  WARN: base graph only; expanded OSM layers not imported"
  echo "        Routes work with base safety_weight only."
elif [[ "$ENRICH_ROWS" -gt 0 && "$ACTIVE_COUNT" -gt 0 ]]; then
  echo "  OK: full enrichment active"
else
  echo "  UNKNOWN: unexpected state"
fi
