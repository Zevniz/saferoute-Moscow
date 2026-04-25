#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8000}"
SMOKE_MODE="${SMOKE_MODE:-basic}"

python3 - "$API_URL" "$SMOKE_MODE" <<'PY'
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

api_url = sys.argv[1].rstrip("/")
mode = sys.argv[2]


def fail(message, *, hint=True):
    print(f"smoke failed: {message}", file=sys.stderr)
    if hint:
        print("", file=sys.stderr)
        print("Start the API process with:", file=sys.stderr)
        print("  npm run dev:api", file=sys.stderr)
        print("", file=sys.stderr)
        print("For full self-hosted routing dependencies, use:", file=sys.stderr)
        print("  npm run self-hosted:preflight", file=sys.stderr)
        print("  npm run self-hosted:up", file=sys.stderr)
        print("or:", file=sys.stderr)
        print("  npm run bootstrap:self-hosted", file=sys.stderr)
    raise SystemExit(1)


def request(path, *, timeout=20, expect_status=200, parse_json=True):
    url = f"{api_url}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode()
            if response.status != expect_status:
                fail(f"{path} returned HTTP {response.status}, expected {expect_status}")
            return response.status, json.loads(body) if parse_json else body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        if exc.code == expect_status:
            return exc.code, json.loads(body) if parse_json and body else body
        fail(f"{path} returned HTTP {exc.code}, expected {expect_status}. Body: {body[:500]}")
    except urllib.error.URLError as exc:
        fail(f"API is not reachable at {api_url}: {exc.reason}")
    except TimeoutError:
        fail(f"timed out waiting for {path} at {api_url}")
    except json.JSONDecodeError as exc:
        fail(f"{path} did not return valid JSON: {exc}")


def metric_value(metrics_text, metric_name, labels):
    label_body = ",".join(f'{key}="{value}"' for key, value in sorted(labels.items()))
    pattern = rf'^{re.escape(metric_name)}\{{{re.escape(label_body)}\}} ([0-9]+(?:\.[0-9]+)?)$'
    for line in metrics_text.splitlines():
        match = re.match(pattern, line)
        if match:
            return float(match.group(1))
    return 0.0


health_path = "/api/health?deep=true" if mode == "full" else "/api/health?deep=false"
_, health = request(health_path, timeout=30)
if health.get("status") not in {"ok", "degraded"}:
    fail(f"{health_path} returned unexpected status payload: {health}", hint=False)

services = health.get("services") or {}
for service_name in ("postgres", "photon", "valhalla"):
    if service_name not in services:
        fail(f"{health_path} is missing service status for {service_name}: {health}", hint=False)

_, metrics_text = request("/api/metrics", timeout=20, parse_json=False)
if "saferoute_http_requests_total" not in metrics_text:
    fail("/api/metrics did not expose saferoute_http_requests_total", hint=False)

_, validation_error = request("/api/search?q=%20%20a%20&limit=5", timeout=20, expect_status=422)
if validation_error.get("detail") != "search query must contain at least 2 non-whitespace characters":
    fail(f"/api/search validation smoke returned unexpected payload: {validation_error}", hint=False)

if mode != "full":
    print(json.dumps({"status": "ok", "mode": "basic", "api": api_url, "health": health["status"]}, ensure_ascii=False))
    raise SystemExit(0)

if health.get("status") != "ok":
    fail(f"self-hosted smoke requires health status ok, got {health}", hint=False)
for name, service in services.items():
    if service.get("status") != "ok":
        fail(f"self-hosted smoke requires {name}=ok, got {service}", hint=False)
for profile, readiness in (health.get("profiles") or {}).items():
    if readiness.get("status") != "ok":
        fail(f"self-hosted smoke requires profile {profile}=ok, got {readiness}", hint=False)

_, search = request("/api/search?q=%D0%9A%D1%80%D0%B5%D0%BC%D0%BB%D1%8C&limit=5", timeout=20)
if not search or search[0].get("label") != "Московский Кремль, Москва":
    fail(f"/api/search did not return the expected Moscow landmark: {search[:1] if isinstance(search, list) else search}", hint=False)

_, cells = request("/api/sidewalk-cells?bbox=37.50,55.68,37.75,55.82&resolution=9", timeout=20)
if cells.get("type") != "FeatureCollection":
    fail(f"/api/sidewalk-cells returned unexpected payload: {cells}", hint=False)

_, metrics_before = request("/api/metrics", timeout=20, parse_json=False)
initial_cache_hits = metric_value(metrics_before, "saferoute_route_cache_total", {"result": "hit"})

pair = {"lat1": 55.7558, "lon1": 37.6173, "lat2": 55.7298, "lon2": 37.6030, "alternatives": 3}
for profile in ("walk", "bike", "car"):
    query = urllib.parse.urlencode({**pair, "profile": profile})
    started = time.perf_counter()
    _, payload = request(f"/api/route?{query}", timeout=90)
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    routes = payload.get("routes", [])
    if not routes:
        fail(f"/api/route returned no routes for {profile}: {payload}", hint=False)
    seen = set()
    for route in routes:
        instructions = route.get("properties", {}).get("instructions") or []
        if not instructions:
            fail(f"/api/route returned a non-navigable route for {profile}: {route}", hint=False)
        if any(not instruction.get("text") or instruction.get("text") == "Следуйте по маршруту" for instruction in instructions):
            fail(f"/api/route returned placeholder instructions for {profile}: {route}", hint=False)
        geometry_key = json.dumps(route.get("geometry"), sort_keys=True, separators=(",", ":"))
        if geometry_key in seen:
            fail(f"/api/route returned duplicate route geometry for {profile}", hint=False)
        seen.add(geometry_key)
    fast = [route for route in routes if route.get("properties", {}).get("variant") == "fast"]
    if fast:
        fastest_eta = min(route["properties"]["estimated_mins"] for route in routes)
        if fast[0]["properties"]["estimated_mins"] != fastest_eta:
            fail(f"/api/route fast variant is not actually fastest for {profile}: {payload}", hint=False)
    print(json.dumps({"profile": profile, "routes": len(routes), "elapsed_ms": elapsed_ms}, ensure_ascii=False))

walk_query = urllib.parse.urlencode({**pair, "profile": "walk"})
_, warm_payload = request(f"/api/route?{walk_query}", timeout=90)
if not warm_payload.get("routes"):
    fail(f"warm walk route returned no routes: {warm_payload}", hint=False)

_, metrics_after = request("/api/metrics", timeout=20, parse_json=False)
if metric_value(metrics_after, "saferoute_route_cache_total", {"result": "hit"}) < initial_cache_hits + 1:
    fail("route cache hit metric did not increase after a repeated walk route", hint=False)

print(json.dumps({"status": "ok", "mode": "full", "api": api_url}, ensure_ascii=False))
PY
