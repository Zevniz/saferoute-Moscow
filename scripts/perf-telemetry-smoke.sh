#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8000}"
PERF_TELEMETRY_ITERATIONS="${PERF_TELEMETRY_ITERATIONS:-10}"
PERF_TELEMETRY_MAX_P95_MS="${PERF_TELEMETRY_MAX_P95_MS:-5000}"

python3 - "$API_URL" "$PERF_TELEMETRY_ITERATIONS" "$PERF_TELEMETRY_MAX_P95_MS" <<'PY'
import json
import statistics
import sys
import time
import urllib.request

api_url = sys.argv[1].rstrip("/")
iterations = int(sys.argv[2])
max_p95_ms = int(sys.argv[3])
path = "/api/sidewalk-cells?bbox=37.50,55.68,37.75,55.82&resolution=9"
latencies = []

for _ in range(iterations):
    started = time.perf_counter()
    with urllib.request.urlopen(f"{api_url}{path}", timeout=20) as response:
        payload = json.loads(response.read().decode())
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise SystemExit(f"perf telemetry smoke failed: invalid sidewalk cells payload {payload}")
    latencies.append(elapsed_ms)

sorted_latencies = sorted(latencies)
p95_index = min(len(sorted_latencies) - 1, round(0.95 * (len(sorted_latencies) - 1)))
p95 = sorted_latencies[p95_index]
result = {
    "status": "ok",
    "api": api_url,
    "iterations": iterations,
    "min_ms": min(latencies),
    "median_ms": round(statistics.median(latencies)),
    "p95_ms": p95,
    "max_ms": max(latencies),
    "threshold_p95_ms": max_p95_ms,
    "note": "Read-path smoke only; write-throughput requires a real captured telemetry fixture.",
}
print(json.dumps(result, ensure_ascii=False))
if p95 > max_p95_ms:
    raise SystemExit(f"perf telemetry smoke failed: p95 {p95}ms exceeds {max_p95_ms}ms")
PY
