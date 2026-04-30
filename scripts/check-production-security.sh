#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8000}"
SAFEROUTE_API_KEY="${SAFEROUTE_API_KEY:-}"
SECURITY_EXPECT_RATE_LIMIT="${SECURITY_EXPECT_RATE_LIMIT:-true}"
SECURITY_RATE_LIMIT_PROBE_COUNT="${SECURITY_RATE_LIMIT_PROBE_COUNT:-4}"

if [[ -z "$SAFEROUTE_API_KEY" ]]; then
  echo "Usage: SAFEROUTE_API_KEY=<dummy-or-real-key> API_URL=http://127.0.0.1:8000 npm run security:production-check" >&2
  echo "The key is sent in headers but never printed." >&2
  exit 1
fi

status_without_key() {
  curl -sS -o /dev/null -w "%{http_code}" "$1"
}

status_with_key() {
  curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $SAFEROUTE_API_KEY" "$1"
}

expect_status() {
  local label="$1"
  local actual="$2"
  local expected="$3"
  if [[ "$actual" != "$expected" ]]; then
    echo "fail: $label returned HTTP $actual, expected $expected" >&2
    exit 1
  fi
  echo "ok: $label returned HTTP $actual"
}

expect_not_status() {
  local label="$1"
  local actual="$2"
  local forbidden="$3"
  if [[ "$actual" == "$forbidden" ]]; then
    echo "fail: $label returned forbidden HTTP $actual" >&2
    exit 1
  fi
  echo "ok: $label returned HTTP $actual"
}

route_url="$API_URL/api/route?lat1=55.7558&lon1=37.6173&lat2=55.7298&lon2=37.6030&profile=walk&mode=safest"

expect_status "shallow health without key" "$(status_without_key "$API_URL/api/health?deep=false")" "200"
expect_status "deep health without key" "$(status_without_key "$API_URL/api/health?deep=true")" "401"
expect_status "route without key" "$(status_without_key "$route_url")" "401"
expect_not_status "route with key" "$(status_with_key "$route_url")" "401"

if [[ "$SECURITY_EXPECT_RATE_LIMIT" == "true" ]]; then
  rate_limit_seen=false
  for _ in $(seq 1 "$SECURITY_RATE_LIMIT_PROBE_COUNT"); do
    status="$(status_with_key "$API_URL/api/metrics")"
    if [[ "$status" == "429" ]]; then
      rate_limit_seen=true
      break
    fi
  done
  if [[ "$rate_limit_seen" != "true" ]]; then
    echo "fail: rate-limit probe did not receive HTTP 429 after $SECURITY_RATE_LIMIT_PROBE_COUNT requests" >&2
    echo "For local verification, run the API with SAFEROUTE_RATE_LIMIT_PER_MINUTE=2 and SECURITY_RATE_LIMIT_PROBE_COUNT=4." >&2
    exit 1
  fi
  echo "ok: rate-limit probe returned HTTP 429"
fi

echo "Production security probe passed for $API_URL"
