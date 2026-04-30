#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8000}"
PERF_ROUTE_ITERATIONS="${PERF_ROUTE_ITERATIONS:-8}"
PERF_ROUTE_COLD_ITERATIONS="${PERF_ROUTE_COLD_ITERATIONS:-3}"
PERF_ROUTE_MAX_P95_MS="${PERF_ROUTE_MAX_P95_MS:-90000}"

python3 - "$API_URL" "$PERF_ROUTE_ITERATIONS" "$PERF_ROUTE_COLD_ITERATIONS" "$PERF_ROUTE_MAX_P95_MS" <<'PY'
import json
import re
import statistics
import sys
import time
import urllib.parse
import urllib.request

api_url = sys.argv[1].rstrip("/")
iterations = int(sys.argv[2])
cold_iterations = int(sys.argv[3])
max_p95_ms = int(sys.argv[4])
pair = {
    "lat1": 55.7558,
    "lon1": 37.6173,
    "lat2": 55.7298,
    "lon2": 37.6030,
    "profile": "walk",
    "mode": "safest",
    "alternatives": 3,
}

def fetch_metrics():
    try:
        with urllib.request.urlopen(f"{api_url}/api/metrics", timeout=20) as response:
            return response.read().decode()
    except Exception:
        return ""


def parse_safe_geometry_counts(metrics_text):
    safe_geometry = {}
    fallbacks = {}
    for line in metrics_text.splitlines():
        if line.startswith("saferoute_safe_geometry_duration_ms_count"):
            scope_match = re.search(r'scope="([^"]+)"', line)
            value = float(line.rsplit(" ", 1)[1])
            scope = scope_match.group(1) if scope_match else "unknown"
            safe_geometry[scope] = safe_geometry.get(scope, 0.0) + value
        elif line.startswith("saferoute_safe_geometry_fallback_total"):
            reason_match = re.search(r'reason="([^"]+)"', line)
            value = float(line.rsplit(" ", 1)[1])
            reason = reason_match.group(1) if reason_match else "unknown"
            fallbacks[reason] = fallbacks.get(reason, 0.0) + value
    return {"safe_geometry": safe_geometry, "fallbacks": fallbacks}


def diff_counts(after, before):
    keys = set(after) | set(before)
    return {key: int(after.get(key, 0) - before.get(key, 0)) for key in sorted(keys) if after.get(key, 0) - before.get(key, 0)}


def percentile_95(latencies):
    sorted_latencies = sorted(latencies)
    p95_index = min(len(sorted_latencies) - 1, round(0.95 * (len(sorted_latencies) - 1)))
    return sorted_latencies[p95_index]


def run_scenario(name, count, *, cold):
    latencies = []
    base_jitter = ((time.time_ns() % 7000) / 7000) * 0.0007 if cold else 0
    for index in range(count):
        scenario_pair = dict(pair)
        if cold:
            # Tiny coordinate jitter avoids the route cache while staying in the same real Moscow corridor.
            scenario_pair["lat2"] = round(pair["lat2"] + base_jitter + (index + 1) * 0.00003, 6)
            scenario_pair["lon2"] = round(pair["lon2"] + base_jitter + (index + 1) * 0.00003, 6)
        query = urllib.parse.urlencode(scenario_pair)
        started = time.perf_counter()
        with urllib.request.urlopen(f"{api_url}/api/route?{query}", timeout=120) as response:
            payload = json.loads(response.read().decode())
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        routes = payload.get("routes") or []
        if not routes:
            raise SystemExit(f"perf route smoke failed: {name} returned no routes")
        score = routes[0].get("properties", {}).get("score", {}).get("total")
        if not isinstance(score, int) or not (0 <= score <= 100):
            raise SystemExit(f"perf route smoke failed: invalid route score {score}")
        latencies.append(elapsed_ms)
    return {
        "iterations": count,
        "min_ms": min(latencies),
        "median_ms": round(statistics.median(latencies)),
        "p95_ms": percentile_95(latencies),
        "max_ms": max(latencies),
    }


# Warm the canonical route so the cached scenario measures the hot path while
# the cold scenario below still forces fresh safe-geometry work.
run_scenario("warmup", 1, cold=False)
before_counts = parse_safe_geometry_counts(fetch_metrics())
cached = run_scenario("cached", iterations, cold=False)
cold = run_scenario("cold", max(1, cold_iterations), cold=True)
after_counts = parse_safe_geometry_counts(fetch_metrics())

result = {
    "status": "ok",
    "api": api_url,
    "cached": cached,
    "cold": cold,
    "safe_geometry_delta": diff_counts(after_counts["safe_geometry"], before_counts["safe_geometry"]),
    "safe_geometry_fallback_delta": diff_counts(after_counts["fallbacks"], before_counts["fallbacks"]),
    "threshold_p95_ms": max_p95_ms,
}
print(json.dumps(result, ensure_ascii=False))
if max(cached["p95_ms"], cold["p95_ms"]) > max_p95_ms:
    raise SystemExit(
        f"perf route smoke failed: p95 cached={cached['p95_ms']}ms cold={cold['p95_ms']}ms exceeds {max_p95_ms}ms"
    )
PY
