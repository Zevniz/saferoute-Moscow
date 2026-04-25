#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PG_PORT="${PG_PORT:-5433}"
PG_DATA="${PGDATA:-$HOME/Library/Application Support/Postgres/var-18}"
PG_BIN="${PG_BIN:-/Applications/Postgres.app/Contents/Versions/latest/bin}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

cd "$ROOT_DIR"

start_postgres() {
  if [[ ! -d "$PG_DATA" || ! -x "$PG_BIN/pg_ctl" ]]; then
    echo "Postgres.app data dir or pg_ctl not found; skipping local Postgres startup."
    return
  fi

  if "$PG_BIN/pg_ctl" -D "$PG_DATA" status >/dev/null 2>&1; then
    echo "Postgres is already running."
    return
  fi

  echo "Starting Postgres on port $PG_PORT..."
  "$PG_BIN/pg_ctl" \
    -D "$PG_DATA" \
    -o "\"-p\" \"$PG_PORT\" \"-c\" \"shared_preload_libraries=auth_permission_dialog\" \"-c\" \"auth_permission_dialog.dialog_executable_path=/Applications/Postgres.app/Contents/MacOS/PostgresPermissionDialog\"" \
    -l "$PG_DATA/postgresql.log" \
    start
}

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

start_postgres

echo "Starting FastAPI on port $BACKEND_PORT..."
DATABASE_URL="${DATABASE_URL:-postgresql://artem@localhost:$PG_PORT/artem}" \
  PHOTON_URL="${PHOTON_URL:-http://localhost:2322}" \
  VALHALLA_URL="${VALHALLA_URL:-http://localhost:8002}" \
  ALLOW_PUBLIC_SERVICE_FALLBACK="${ALLOW_PUBLIC_SERVICE_FALLBACK:-true}" \
  PORT="$BACKEND_PORT" \
  ./venv/bin/python main.py &
BACKEND_PID=$!

echo "Starting Vite on port $FRONTEND_PORT..."
npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" &
FRONTEND_PID=$!

echo "SafeRoute dev is starting:"
echo "  Frontend: http://127.0.0.1:$FRONTEND_PORT"
echo "  API:      http://localhost:$BACKEND_PORT"

wait "$BACKEND_PID" "$FRONTEND_PID"
