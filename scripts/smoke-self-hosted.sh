#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8000}"

SMOKE_MODE=full API_URL="$API_URL" bash scripts/smoke-api.sh
