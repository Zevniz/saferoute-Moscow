"""In-process Prometheus metrics for the local Platform Core runtime."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Iterable, Tuple, TypedDict

LabelSet = Tuple[Tuple[str, str], ...]


class Histogram(TypedDict):
    buckets: tuple[float, ...]
    counts: dict[float, int]
    count: int
    sum: float


_LOCK = threading.Lock()
_COUNTERS: dict[tuple[str, LabelSet], float] = defaultdict(float)
_HISTOGRAMS: dict[tuple[str, LabelSet], Histogram] = {}
_DEFAULT_BUCKETS = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, float("inf"))


def _labels(labels: dict[str, object] | None) -> LabelSet:
    return tuple(sorted((str(key), str(value)) for key, value in (labels or {}).items()))


def _format_labels(labels: LabelSet, extra: dict[str, object] | None = None) -> str:
    merged = dict(labels)
    if extra:
        merged.update({str(key): str(value) for key, value in extra.items()})
    if not merged:
        return ""
    body = ",".join(f'{key}="{_escape_label_value(value)}"' for key, value in sorted(merged.items()))
    return "{" + body + "}"


def _escape_label_value(value: object) -> str:
    """Escape a Prometheus label value."""

    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def inc(name: str, labels: dict[str, object] | None = None, amount: float = 1.0) -> None:
    """Increment a Prometheus counter."""

    with _LOCK:
        _COUNTERS[(name, _labels(labels))] += amount


def observe(name: str, value: float, labels: dict[str, object] | None = None, buckets: Iterable[float] = _DEFAULT_BUCKETS) -> None:
    """Observe a value in a cumulative Prometheus histogram."""

    label_set = _labels(labels)
    bucket_values = tuple(buckets)
    with _LOCK:
        histogram = _HISTOGRAMS.setdefault(
            (name, label_set),
            {"buckets": bucket_values, "counts": {bucket: 0 for bucket in bucket_values}, "count": 0, "sum": 0.0},
        )
        histogram["count"] = int(histogram["count"]) + 1
        histogram["sum"] = float(histogram["sum"]) + value
        counts = histogram["counts"]
        for bucket in bucket_values:
            if value <= bucket:
                counts[bucket] += 1


def render_prometheus() -> str:
    """Render all in-process metrics in Prometheus text exposition format."""

    lines: list[str] = [
        "# HELP saferoute_http_requests_total HTTP requests handled by SafeRoute.",
        "# TYPE saferoute_http_requests_total counter",
        "# HELP saferoute_http_request_duration_ms HTTP request duration in milliseconds.",
        "# TYPE saferoute_http_request_duration_ms histogram",
        "# HELP saferoute_dependency_requests_total Dependency requests by service/source/status.",
        "# TYPE saferoute_dependency_requests_total counter",
        "# HELP saferoute_dependency_latency_ms Dependency request latency in milliseconds.",
        "# TYPE saferoute_dependency_latency_ms histogram",
        "# HELP saferoute_route_cache_total Route cache hits and misses.",
        "# TYPE saferoute_route_cache_total counter",
        "# HELP saferoute_safe_geometry_fallback_total Safe geometry bounded-route fallbacks by reason.",
        "# TYPE saferoute_safe_geometry_fallback_total counter",
        "# HELP saferoute_safe_geometry_duration_ms Safe geometry pgRouting duration in milliseconds.",
        "# TYPE saferoute_safe_geometry_duration_ms histogram",
        "# HELP saferoute_route_variants_total Route responses by profile and variant.",
        "# TYPE saferoute_route_variants_total counter",
        "# HELP saferoute_route_failures_total Route failures grouped by reason.",
        "# TYPE saferoute_route_failures_total counter",
        "# HELP saferoute_weather_requests_total Optional weather provider requests by provider/status.",
        "# TYPE saferoute_weather_requests_total counter",
        "# HELP saferoute_weather_latency_ms Optional weather provider latency in milliseconds.",
        "# TYPE saferoute_weather_latency_ms histogram",
        "# HELP saferoute_telemetry_confidence_total Route telemetry-confidence lookups by status.",
        "# TYPE saferoute_telemetry_confidence_total counter",
        "# HELP saferoute_telemetry_confidence_route_cells Route H3 cell count sampled for telemetry confidence.",
        "# TYPE saferoute_telemetry_confidence_route_cells histogram",
    ]

    with _LOCK:
        for (name, labels), value in sorted(_COUNTERS.items()):
            lines.append(f"{name}{_format_labels(labels)} {value:g}")

        for (name, labels), histogram in sorted(_HISTOGRAMS.items()):
            for bucket in histogram["buckets"]:
                le = "+Inf" if bucket == float("inf") else str(bucket)
                lines.append(f'{name}_bucket{_format_labels(labels, {"le": le})} {histogram["counts"][bucket]}')
            lines.append(f"{name}_count{_format_labels(labels)} {histogram['count']}")
            lines.append(f"{name}_sum{_format_labels(labels)} {float(histogram['sum']):.6f}")

    return "\n".join(lines) + "\n"
