"""Optional public-launch request hardening.

Local/self-hosted defaults stay public. Production deployments can enable
API-key checks and per-process rate limits through env flags without changing
the public route/search/telemetry contracts.
"""

from __future__ import annotations

import time
from hashlib import sha256
from hmac import compare_digest
from dataclasses import dataclass
from threading import Lock

from fastapi import HTTPException, Request

from app.core.config import get_settings


@dataclass
class RateCounter:
    """One in-memory fixed-window rate counter."""

    window_started: float
    count: int


_RATE_LIMIT_STATE: dict[tuple[str, str], RateCounter] = {}
_RATE_LIMIT_LOCK = Lock()


def reset_rate_limit_state() -> None:
    """Clear in-memory counters for tests and process reloads."""

    with _RATE_LIMIT_LOCK:
        _RATE_LIMIT_STATE.clear()


def request_token(request: Request) -> str | None:
    """Extract an API token without logging or transforming it."""

    header_value = request.headers.get("authorization", "")
    if header_value.lower().startswith("bearer "):
        token = header_value[7:].strip()
        return token or None
    token = request.headers.get("x-saferoute-api-key")
    return token.strip() if token and token.strip() else None


def client_identity(request: Request) -> str:
    """Return a coarse client identity suitable for local in-process limits."""

    token = request_token(request)
    if token:
        return f"api-key:{sha256(token.encode('utf-8')).hexdigest()[:16]}"
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def ensure_api_key(request: Request, *, required: bool, allow_global: bool = True) -> None:
    """Enforce optional API-key auth for selected endpoint groups."""

    settings = get_settings()
    global_required = allow_global and getattr(settings, "saferoute_require_api_key", False)
    effective_required = required or global_required
    auth_enabled = settings.public_api_key_auth_enabled or effective_required
    if not auth_enabled or not effective_required:
        return

    allowed_keys = settings.public_api_keys
    if not allowed_keys:
        raise HTTPException(status_code=503, detail="API key protection is enabled but no API keys are configured")

    token = request_token(request) or ""
    if not any(compare_digest(token, allowed_key) for allowed_key in allowed_keys):
        raise HTTPException(status_code=401, detail="API key required")


def rate_limit_for_bucket(bucket: str) -> int:
    """Return the configured fixed-window limit for an endpoint bucket."""

    settings = get_settings()
    return {
        "route": settings.rate_limit_route_per_window,
        "geocode": settings.rate_limit_geocode_per_window,
        "telemetry": settings.rate_limit_telemetry_per_window,
        "tiles": settings.rate_limit_tiles_per_window,
        "metrics": settings.rate_limit_metrics_per_window,
        "health": settings.rate_limit_health_per_window,
    }.get(bucket, settings.rate_limit_route_per_window)


def enforce_rate_limit(request: Request, bucket: str) -> None:
    """Apply a conservative in-process fixed-window rate limit when enabled."""

    settings = get_settings()
    if not settings.rate_limit_enabled:
        return

    limit = rate_limit_for_bucket(bucket)
    window_seconds = settings.rate_limit_window_seconds
    now = time.monotonic()
    key = (bucket, client_identity(request))
    with _RATE_LIMIT_LOCK:
        counter = _RATE_LIMIT_STATE.get(key)
        if counter is None or now - counter.window_started >= window_seconds:
            _RATE_LIMIT_STATE[key] = RateCounter(window_started=now, count=1)
            return
        counter.count += 1
        if counter.count > limit:
            raise HTTPException(status_code=429, detail="rate limit exceeded")


def enforce_content_length(request: Request, max_bytes: int) -> None:
    """Reject clearly oversized requests before expensive processing."""

    content_length = request.headers.get("content-length")
    if not content_length:
        return
    try:
        body_size = int(content_length)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid content-length header") from None
    if body_size > max_bytes:
        raise HTTPException(status_code=413, detail="request body too large")


def protect_metrics(request: Request) -> None:
    ensure_api_key(request, required=get_settings().require_api_key_for_metrics)
    enforce_rate_limit(request, "metrics")


def protect_health(request: Request, *, deep: bool) -> None:
    ensure_api_key(request, required=deep and get_settings().require_api_key_for_deep_health, allow_global=deep)
    enforce_rate_limit(request, "health")


def protect_geocode(request: Request) -> None:
    ensure_api_key(request, required=False)
    enforce_rate_limit(request, "geocode")


def protect_route(request: Request) -> None:
    ensure_api_key(request, required=False)
    enforce_rate_limit(request, "route")


def protect_tiles(request: Request) -> None:
    ensure_api_key(request, required=get_settings().require_api_key_for_tiles)
    enforce_rate_limit(request, "tiles")


def protect_telemetry_write(request: Request) -> None:
    settings = get_settings()
    ensure_api_key(request, required=settings.require_api_key_for_telemetry_write)
    enforce_content_length(request, settings.telemetry_max_body_bytes)
    enforce_rate_limit(request, "telemetry")
