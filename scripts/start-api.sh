#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"

cd "$ROOT_DIR"

redact_url() {
  sed -E 's#(postgres(ql)?://[^:/@]+):[^@]*@#\1:***@#' <<<"$1"
}

if [[ ! -x ./venv/bin/python ]]; then
  echo "Missing ./venv/bin/python." >&2
  echo "Create the local environment first:" >&2
  echo "  python3 -m venv venv" >&2
  echo "  ./venv/bin/python -m pip install -r requirements.txt" >&2
  exit 1
fi

echo "Starting SafeRoute FastAPI on http://127.0.0.1:$BACKEND_PORT"
echo "Dependency defaults:"
echo "  DATABASE_URL=$(redact_url "${DATABASE_URL:-postgresql://artem@localhost:5433/artem}")"
echo "  PHOTON_URL=${PHOTON_URL:-http://localhost:2322}"
echo "  VALHALLA_URL=${VALHALLA_URL:-http://localhost:8002}"
echo
echo "This starts the API process only. For production-like dependencies, run:"
echo "  docker compose up"
echo "or:"
echo "  npm run bootstrap:self-hosted"
echo

PORT="$BACKEND_PORT" ./venv/bin/python main.py
