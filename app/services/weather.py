"""Optional route-level weather risk from real provider data."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from app.core.config import get_settings
from app.core.metrics import inc, observe
from app.services.geometry import flatten_geometry_coordinates
from app.services.http import request_json


@dataclass(frozen=True)
class WeatherRisk:
    """Current route-level weather risk and public source metadata."""

    risk: float
    confidence: float
    source: dict[str, object]


_WEATHER_CACHE: dict[Tuple[str, float, float], Tuple[float, WeatherRisk]] = {}
OPEN_METEO_PROVIDER = "open_meteo"
OPEN_METEO_FIELDS = (
    "temperature_2m",
    "precipitation",
    "rain",
    "snowfall",
    "weather_code",
    "wind_gusts_10m",
    "visibility",
)


def _float_value(payload: dict[str, Any], key: str) -> float | None:
    value = payload.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def route_bbox_centroid(geometry: Dict[str, Any]) -> tuple[float, float] | None:
    """Return `(lat, lon)` at the route geometry bounding-box centroid."""

    coordinates = flatten_geometry_coordinates(geometry)
    if not coordinates:
        return None
    lon_values = [float(point[0]) for point in coordinates if len(point) >= 2]
    lat_values = [float(point[1]) for point in coordinates if len(point) >= 2]
    if not lon_values or not lat_values:
        return None
    return (min(lat_values) + max(lat_values)) / 2.0, (min(lon_values) + max(lon_values)) / 2.0


def route_midpoint(geometry: Dict[str, Any]) -> tuple[float, float] | None:
    """Backward-compatible alias for the weather sample point."""

    return route_bbox_centroid(geometry)


def calculate_open_meteo_risk(current: dict[str, Any]) -> float:
    """Convert real Open-Meteo current weather fields to a bounded risk score."""

    precipitation = _float_value(current, "precipitation") or 0.0
    rain = _float_value(current, "rain") or 0.0
    snowfall = _float_value(current, "snowfall") or 0.0
    temperature = _float_value(current, "temperature_2m")
    wind_gusts = _float_value(current, "wind_gusts_10m") or 0.0
    visibility = _float_value(current, "visibility")
    weather_code = _float_value(current, "weather_code")

    risk = 0.0
    if precipitation >= 2.0 or rain >= 2.0:
        risk += 0.35
    elif precipitation > 0.0 or rain > 0.0:
        risk += 0.18

    if snowfall >= 0.2:
        risk += 0.4
    if temperature is not None and temperature <= 0.0 and (precipitation > 0.0 or rain > 0.0 or snowfall > 0.0):
        risk += 0.25
    if wind_gusts >= 50.0:
        risk += 0.28
    elif wind_gusts >= 35.0:
        risk += 0.14
    if visibility is not None and visibility < 1000.0:
        risk += 0.25
    if weather_code is not None and weather_code >= 95:
        risk += 0.45

    return round(min(max(risk, 0.0), 1.0), 3)


def get_route_weather_risk(geometry: Dict[str, Any]) -> WeatherRisk | None:
    """Fetch optional real weather risk for a route, disabled by default."""

    settings = get_settings()
    if not settings.weather_enabled:
        return None
    if settings.weather_provider != OPEN_METEO_PROVIDER:
        return None
    sample_point = route_bbox_centroid(geometry)
    if sample_point is None:
        return None
    lat, lon = sample_point
    cache_key = (settings.weather_provider, round(lat, 3), round(lon, 3))
    cached = _WEATHER_CACHE.get(cache_key)
    now = time.time()
    if cached and cached[0] > now:
        inc("saferoute_weather_requests_total", {"provider": settings.weather_provider, "status": "cache_hit"})
        return cached[1]

    params = {
        "latitude": round(lat, 5),
        "longitude": round(lon, 5),
        "current": ",".join(OPEN_METEO_FIELDS),
        "timezone": "UTC",
    }
    started = time.perf_counter()
    try:
        payload, latency_ms = request_json(
            "GET",
            settings.weather_url,
            params=params,
            timeout_seconds=settings.weather_timeout_seconds,
            connect_timeout_seconds=min(settings.http_connect_timeout_seconds, settings.weather_timeout_seconds),
        )
    except Exception:
        observe(
            "saferoute_weather_latency_ms",
            round((time.perf_counter() - started) * 1000, 2),
            {"provider": settings.weather_provider, "status": "error"},
        )
        inc("saferoute_weather_requests_total", {"provider": settings.weather_provider, "status": "error"})
        return None

    current = payload.get("current")
    if not isinstance(current, dict):
        inc("saferoute_weather_requests_total", {"provider": settings.weather_provider, "status": "invalid"})
        return None
    if not any(_float_value(current, key) is not None for key in OPEN_METEO_FIELDS):
        inc("saferoute_weather_requests_total", {"provider": settings.weather_provider, "status": "invalid"})
        return None

    risk = calculate_open_meteo_risk(current)
    confidence = 1.0
    weather = WeatherRisk(
        risk=risk,
        confidence=confidence,
        source={
            "active": True,
            "provider": OPEN_METEO_PROVIDER,
            "provider_label": "Open-Meteo",
            "source_url": "https://open-meteo.com/en/docs",
            "attribution": "Weather data by Open-Meteo.com",
            "license": "CC BY 4.0",
            "license_url": "https://open-meteo.com/en/licence",
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "sample_method": "route_bbox_centroid",
            "cache_ttl_seconds": settings.weather_cache_ttl_seconds,
            "timeout_seconds": settings.weather_timeout_seconds,
            "risk": risk,
            "confidence": confidence,
            "current": {
                key: current.get(key)
                for key in OPEN_METEO_FIELDS
                if key in current
            },
        },
    )
    _WEATHER_CACHE[cache_key] = (now + settings.weather_cache_ttl_seconds, weather)
    observe("saferoute_weather_latency_ms", latency_ms, {"provider": settings.weather_provider, "status": "ok"})
    inc("saferoute_weather_requests_total", {"provider": settings.weather_provider, "status": "ok"})
    return weather
