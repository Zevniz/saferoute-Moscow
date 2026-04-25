"""Lightweight JSON request logging for the API gateway."""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Awaitable, Callable

from fastapi import Request, Response

from app.core.metrics import inc, observe


logger = logging.getLogger("saferoute")
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def configure_logging() -> None:
    """Configure process-wide JSON-ish application logging."""

    logging.basicConfig(level=logging.INFO, format="%(message)s")


def log_event(event: str, **fields: object) -> None:
    """Emit one structured log event."""

    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, ensure_ascii=False, default=str))


def metric_path(request: Request) -> str:
    """Return a low-cardinality path label for request metrics."""

    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    return str(route_path or request.url.path)


async def request_logging_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Attach request IDs and log duration/status for every HTTP request."""

    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    response: Response | None = None
    try:
        result = await call_next(request)
        response = result
        return result
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        status_code = response.status_code if response else 500
        path = metric_path(request)
        inc(
            "saferoute_http_requests_total",
            {"method": request.method, "path": path, "status": status_code},
        )
        observe(
            "saferoute_http_request_duration_ms",
            duration_ms,
            {"method": request.method, "path": path, "status": status_code},
        )
        log_event(
            "http_request",
            request_id=request_id,
            method=request.method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
        )
        if response is not None:
            response.headers["x-request-id"] = request_id
        request_id_var.reset(token)
