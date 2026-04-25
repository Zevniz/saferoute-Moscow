"""HTTP client helpers for external routing/geocoding services."""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any, Dict, Iterable, Optional, Tuple

import httpx

from app.core.config import get_settings
from app.core.metrics import inc, observe
from app.core.observability import request_id_var


class DependencyCallError(RuntimeError):
    """Raised when all configured URLs for a dependency fail."""

    def __init__(self, service: str, detail: str, latency_ms: float | None = None) -> None:
        super().__init__(detail)
        self.service = service
        self.detail = detail
        self.latency_ms = latency_ms


@lru_cache
def get_http_client(timeout_seconds: float, connect_timeout_seconds: float, user_agent: str) -> httpx.Client:
    """Return a pooled HTTP client for dependency calls."""

    timeout = httpx.Timeout(timeout_seconds, connect=connect_timeout_seconds)
    return httpx.Client(timeout=timeout, headers={"User-Agent": user_agent})


def request_json(
    method: str,
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Any] = None,
) -> Tuple[Dict[str, Any], float]:
    """Request JSON from one URL and return payload plus latency."""

    settings = get_settings()
    client = get_http_client(settings.http_timeout_seconds, settings.http_connect_timeout_seconds, settings.http_user_agent)
    headers = {}
    request_id = request_id_var.get()
    if request_id:
        headers["x-request-id"] = request_id
    started = time.perf_counter()
    response = client.request(method, url, params=params, json=json_body, headers=headers)
    response.raise_for_status()
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("dependency returned non-object JSON")
    return payload, latency_ms


def dependency_urls(service: str) -> Iterable[str]:
    """Return primary and optional dev fallback URLs for a dependency."""

    settings = get_settings()
    if service == "photon":
        yield settings.photon_url.rstrip("/")
        if settings.allow_public_service_fallback and settings.public_photon_url.rstrip("/") != settings.photon_url.rstrip("/"):
            yield settings.public_photon_url.rstrip("/")
        return
    if service == "valhalla":
        yield settings.valhalla_url.rstrip("/")
        if settings.allow_public_service_fallback and settings.public_valhalla_url.rstrip("/") != settings.valhalla_url.rstrip("/"):
            yield settings.public_valhalla_url.rstrip("/")
        return
    raise ValueError(f"Unknown dependency service: {service}")


def fetch_dependency_json(
    service: str,
    method: str,
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Any] = None,
) -> Tuple[Dict[str, Any], float, str]:
    """Fetch JSON from a dependency, using optional dev fallback if enabled."""

    settings = get_settings()
    last_error: Exception | None = None
    last_latency: float | None = None
    for base_url in dependency_urls(service):
        url = f"{base_url}{path}"
        for attempt in range(max(1, settings.http_retry_attempts)):
            started = time.perf_counter()
            try:
                payload, latency_ms = request_json(method, url, params=params, json_body=json_body)
                source = "fallback" if base_url not in {settings.photon_url.rstrip("/"), settings.valhalla_url.rstrip("/")} else "primary"
                inc("saferoute_dependency_requests_total", {"service": service, "source": source, "status": "ok"})
                observe("saferoute_dependency_latency_ms", latency_ms, {"service": service, "source": source, "status": "ok"})
                return payload, latency_ms, base_url
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                last_latency = round((time.perf_counter() - started) * 1000, 2)
                source = "fallback" if base_url not in {settings.photon_url.rstrip("/"), settings.valhalla_url.rstrip("/")} else "primary"
                inc("saferoute_dependency_requests_total", {"service": service, "source": source, "status": "error"})
                observe("saferoute_dependency_latency_ms", last_latency, {"service": service, "source": source, "status": "error"})
                if attempt + 1 < max(1, settings.http_retry_attempts):
                    time.sleep(settings.http_retry_backoff_seconds * (attempt + 1))
                continue

    detail = str(last_error.__class__.__name__) if last_error else "dependency unavailable"
    raise DependencyCallError(service=service, detail=detail, latency_ms=last_latency)
