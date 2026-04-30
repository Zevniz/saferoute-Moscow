#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8000}"

python3 - "$API_URL" <<'PY'
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

api_url = sys.argv[1].rstrip("/")
modes = ("safest", "fastest", "balanced", "accessible")
cases = [
    {
        "name": "central_walk_kremlin_muzeon",
        "profile": "walk",
        "lat1": 55.7520233,
        "lon1": 37.6174994,
        "lat2": 55.729804,
        "lon2": 37.603033,
    },
    {
        "name": "garden_ring_bike",
        "profile": "bike",
        "lat1": 55.7558,
        "lon1": 37.6173,
        "lat2": 55.7415,
        "lon2": 37.6208,
    },
    {
        "name": "north_center_car",
        "profile": "car",
        "lat1": 55.7903,
        "lon1": 37.5581,
        "lat2": 55.7520,
        "lon2": 37.6175,
    },
    {
        "name": "short_accessible_center",
        "profile": "walk",
        "lat1": 55.7601,
        "lon1": 37.6187,
        "lat2": 55.7576,
        "lon2": 37.6260,
    },
]


def fail(message):
    print(f"route corpus failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def request_route(case, mode):
    params = urllib.parse.urlencode({**case, "mode": mode, "alternatives": 3})
    url = f"{api_url}/api/route?{params}"
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        fail(f"{case['name']} {mode} returned HTTP {exc.code}: {body[:500]}")
    except urllib.error.URLError as exc:
        fail(f"API unreachable at {api_url}: {exc.reason}")
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    return payload, elapsed_ms


results = []
for case in cases:
    for mode in modes:
        payload, elapsed_ms = request_route(case, mode)
        routes = payload.get("routes")
        if not isinstance(routes, list) or not (1 <= len(routes) <= 3):
            fail(f"{case['name']} {mode} returned invalid route count: {payload}")
        if payload.get("meta", {}).get("mode") != mode:
            fail(f"{case['name']} {mode} did not preserve mode in meta: {payload.get('meta')}")
        for route in routes:
            properties = route.get("properties") or {}
            score = properties.get("score") or {}
            geometry = route.get("geometry") or {}
            coordinates = geometry.get("coordinates") or []
            if geometry.get("type") != "LineString" or len(coordinates) < 2:
                fail(f"{case['name']} {mode} returned invalid geometry")
            if not isinstance(score.get("total"), int) or not (0 <= score["total"] <= 100):
                fail(f"{case['name']} {mode} returned invalid score: {score}")
            enrichment = (score.get("data_sources") or {}).get("enrichment") or {}
            weather = (score.get("data_sources") or {}).get("weather") or {}
            active_factors = set(enrichment.get("active_factors") or [])
            factors = score.get("factors") or {}
            unavailable_factor_map = {
                "curb_risk": ["avg_curb_risk", "max_curb_frequency", "max_curb_density_per_km"],
                "crossing_count": ["crossing_count"],
                "traffic_intensity": ["avg_traffic_intensity"],
                "road_exposure_proxy": ["avg_road_exposure_proxy"],
                "pedestrian_density": ["avg_pedestrian_density"],
                "micromobility_allowed": [
                    "micromobility_forbidden_fraction",
                    "forbidden_zone_fraction",
                    "micromobility_slow_zone_fraction",
                    "min_zone_speed_limit_kmh",
                ],
                "telemetry_confidence": ["avg_telemetry_confidence"],
            }
            for source_factor, score_factor_names in unavailable_factor_map.items():
                if source_factor in active_factors:
                    continue
                for score_factor_name in score_factor_names:
                    if factors.get(score_factor_name) is not None:
                        fail(
                            f"{case['name']} {mode} returned unavailable factor {score_factor_name} "
                            f"without active source factor {source_factor}: {factors.get(score_factor_name)}"
                        )
            if not weather.get("active") and factors.get("avg_weather_sensitive_risk") is not None:
                fail(
                    f"{case['name']} {mode} returned weather risk without an active weather source: "
                    f"{factors.get('avg_weather_sensitive_risk')}"
                )
            if not isinstance(properties.get("safety_index"), int):
                fail(f"{case['name']} {mode} missing integer safety_index")
            reasons = score.get("reasons") or []
            if not reasons or not all({"code", "impact", "value", "weight"} <= set(reason) for reason in reasons):
                fail(f"{case['name']} {mode} returned invalid score reasons: {score}")
        results.append(
            {
                "case": case["name"],
                "profile": case["profile"],
                "mode": mode,
                "routes": len(routes),
                "elapsed_ms": elapsed_ms,
                "scores": [route["properties"]["score"]["total"] for route in routes],
            }
        )

print(json.dumps({"status": "ok", "api": api_url, "cases": results}, ensure_ascii=False))
PY
