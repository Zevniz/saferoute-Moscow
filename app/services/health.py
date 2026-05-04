"""Dependency health and readiness checks."""

from __future__ import annotations

import time
from typing import Dict
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.db import get_engine
from app.schemas.routing import DependencyStatus, HealthResponse, HealthRuntime, ProfileReadiness
from app.services.http import DependencyCallError, fetch_dependency_json
from app.services.routing import build_route_request, encode_query_json
from app.services.search import MOSCOW_CENTER


def redact_url_credentials(url: str) -> str:
    """Return a URL safe for health responses by hiding passwords."""

    try:
        parts = urlsplit(url)
        hostname = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
    except ValueError:
        return "<invalid url>"

    if not parts.netloc or parts.password is None:
        return url

    host = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
    username = parts.username or ""
    userinfo = f"{username}:***@" if username else "***@"
    return urlunsplit((parts.scheme, f"{userinfo}{host}{port}", parts.path, parts.query, parts.fragment))


def timed_status(fn) -> tuple[str, str | None, float | None]:
    """Run one health check and convert exceptions into status tuples."""

    started = time.perf_counter()
    try:
        fn()
        return "ok", None, round((time.perf_counter() - started) * 1000, 2)
    except Exception as exc:  # noqa: BLE001 - health needs to report dependency classes.
        return "error", exc.__class__.__name__, round((time.perf_counter() - started) * 1000, 2)


def timed_dependency_source(fn, primary_url: str) -> tuple[str, str | None, float | None]:
    """Run a dependency check and mark optional public fallback usage as degraded."""

    started = time.perf_counter()
    try:
        source_url = fn().rstrip("/")
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        if source_url != primary_url.rstrip("/"):
            return "fallback", f"using {source_url}", latency_ms
        return "ok", None, latency_ms
    except Exception as exc:  # noqa: BLE001 - health needs dependency failure classes.
        return "error", exc.__class__.__name__, round((time.perf_counter() - started) * 1000, 2)


def check_postgres() -> DependencyStatus:
    """Check DB connectivity and required safety graph presence."""

    settings = get_settings()

    def run() -> None:
        with get_engine().connect() as conn:
            exists = conn.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name = 'moscow_network'
                    )
                    """
                )
            ).scalar()
            if not exists:
                raise RuntimeError("moscow_network table is missing")

    status, detail, latency_ms = timed_status(run)
    return DependencyStatus(status=status, url=redact_url_credentials(settings.database_url), detail=detail, latency_ms=latency_ms)


def check_photon() -> DependencyStatus:
    """Check Photon search readiness."""

    settings = get_settings()

    def run() -> str:
        _, _, source_url = fetch_dependency_json(
            "photon",
            "GET",
            "/api",
            params={"q": "Москва", "limit": 1, "lat": MOSCOW_CENTER["lat"], "lon": MOSCOW_CENTER["lon"]},
        )
        return source_url

    status, detail, latency_ms = timed_dependency_source(run, settings.photon_url)
    return DependencyStatus(status=status, url=settings.photon_url, detail=detail, latency_ms=latency_ms)


def check_valhalla() -> DependencyStatus:
    """Check Valhalla service readiness with a lightweight pedestrian route."""

    settings = get_settings()

    def run() -> str:
        payload = build_route_request(
            "walk",
            MOSCOW_CENTER["lat"],
            MOSCOW_CENTER["lon"],
            MOSCOW_CENTER["lat"] + 0.002,
            MOSCOW_CENTER["lon"] + 0.002,
            1,
        )
        _, _, source_url = fetch_dependency_json("valhalla", "GET", "/route", params={"json": encode_query_json(payload)})
        return source_url

    status, detail, latency_ms = timed_dependency_source(run, settings.valhalla_url)
    return DependencyStatus(status=status, url=settings.valhalla_url, detail=detail, latency_ms=latency_ms)


def check_profile_readiness(profile: str) -> ProfileReadiness:
    """Check whether Valhalla can build a route for one live UI profile."""

    settings = get_settings()

    def run() -> str:
        payload = build_route_request(
            profile,
            MOSCOW_CENTER["lat"],
            MOSCOW_CENTER["lon"],
            MOSCOW_CENTER["lat"] + 0.002,
            MOSCOW_CENTER["lon"] + 0.002,
            1,
        )
        _, _, source_url = fetch_dependency_json("valhalla", "GET", "/route", params={"json": encode_query_json(payload)})
        return source_url

    status, detail, latency_ms = timed_dependency_source(run, settings.valhalla_url)
    return ProfileReadiness(status=status, detail=detail, latency_ms=latency_ms)


def build_runtime_readiness(
    status: str,
    services: Dict[str, DependencyStatus],
    profiles: Dict[str, ProfileReadiness],
) -> HealthRuntime:
    """Describe whether this runtime is production-like without hiding fallback state."""

    settings = get_settings()
    checked = [*services.values(), *profiles.values()]
    has_fallback = any(item.status == "fallback" for item in checked)
    production_like = not settings.allow_public_service_fallback and not has_fallback
    if status != "ok":
        readiness = "dev_fallback" if has_fallback else "degraded"
        detail = "One or more dependencies are unavailable or using a development fallback."
    elif has_fallback:
        readiness = "dev_fallback"
        detail = "A public dependency fallback is serving traffic; this is local-dev-only."
    elif settings.allow_public_service_fallback:
        readiness = "local_dev_ready"
        detail = "Dependencies are healthy, but public fallback is enabled for local development."
    else:
        readiness = "self_hosted_ready"
        detail = "All checked dependencies are primary self-hosted services."

    return HealthRuntime(
        environment=settings.environment,
        public_fallback_allowed=settings.allow_public_service_fallback,
        production_like=production_like,
        readiness=readiness,
        detail=detail,
    )


def dependency_status(deep: bool = True) -> HealthResponse:
    """Return dependency and optional per-profile readiness."""

    services: Dict[str, DependencyStatus] = {
        "postgres": check_postgres(),
        "photon": check_photon(),
        "valhalla": check_valhalla(),
    }
    profiles: Dict[str, ProfileReadiness] = {}
    if deep and get_settings().health_route_readiness:
        profiles = {profile: check_profile_readiness(profile) for profile in ("walk", "bike", "car")}

    ok_services = all(service.status == "ok" for service in services.values())
    ok_profiles = all(profile.status == "ok" for profile in profiles.values()) if profiles else True
    status = "ok" if ok_services and ok_profiles else "degraded"
    return HealthResponse(
        status=status,
        services=services,
        profiles=profiles,
        runtime=build_runtime_readiness(status, services, profiles),
    )
