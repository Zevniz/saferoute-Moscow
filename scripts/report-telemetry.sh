#!/usr/bin/env bash
set -euo pipefail

PSQL_BIN="${PSQL_BIN:-psql}"
HOST_DATABASE_URL="${HOST_DATABASE_URL:-postgresql://artem@localhost:5433/artem}"
COMPOSE_DATABASE_URL="${COMPOSE_DATABASE_URL:-postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db}"

redact_url() {
  printf "%s" "$1" | sed -E 's#(postgres(ql)?://[^:/@]+:)[^@]+@#\1***@#'
}

if ! command -v "$PSQL_BIN" >/dev/null 2>&1; then
  echo "psql not found. Set PSQL_BIN or install PostgreSQL client tools." >&2
  exit 1
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  if PGCONNECT_TIMEOUT=2 "$PSQL_BIN" "$COMPOSE_DATABASE_URL" -Atqc "SELECT 1" >/dev/null 2>&1; then
    DATABASE_URL="$COMPOSE_DATABASE_URL"
  else
    DATABASE_URL="$HOST_DATABASE_URL"
  fi
fi

echo "SafeRoute telemetry report for $(redact_url "$DATABASE_URL")"

"$PSQL_BIN" "$DATABASE_URL" -P pager=off -c "
SELECT
  'sidewalk_samples' AS table_name,
  count(*) AS rows,
  min(captured_at) AS first_observation_at,
  max(captured_at) AS latest_observation_at
FROM public.sidewalk_samples
UNION ALL
SELECT
  'sidewalk_cell_aggregates',
  count(*),
  min(first_seen_at),
  max(last_seen_at)
FROM public.sidewalk_cell_aggregates;
"

"$PSQL_BIN" "$DATABASE_URL" -P pager=off -c "
SELECT
  source,
  count(*) AS rows,
  round(avg(confidence)::numeric, 3) AS avg_sensor_confidence,
  round(avg(quality_score)::numeric, 2) AS avg_quality_score,
  min(captured_at) AS first_observation_at,
  max(captured_at) AS latest_observation_at
FROM public.sidewalk_samples
GROUP BY source
ORDER BY rows DESC;
"

"$PSQL_BIN" "$DATABASE_URL" -P pager=off -c "
SELECT
  h3_resolution,
  count(*) AS cells,
  sum(sample_count) AS samples,
  round(avg(confidence_sum / NULLIF(sample_count, 0))::numeric, 3) AS avg_cell_confidence,
  min(first_seen_at) AS first_observation_at,
  max(last_seen_at) AS latest_observation_at
FROM public.sidewalk_cell_aggregates
GROUP BY h3_resolution
ORDER BY h3_resolution;
"
