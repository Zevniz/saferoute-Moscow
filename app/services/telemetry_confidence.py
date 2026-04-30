"""Route-level confidence from real sidewalk telemetry observations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.metrics import inc, observe
from app.services.geometry import flatten_geometry_coordinates
from app.services.telemetry import h3_latlng_to_cell

ROUTE_SAMPLE_STEP_METERS = 100.0
MAX_ROUTE_SAMPLE_POINTS = 240
MIN_COVERAGE_FRACTION = 0.05
FULL_COUNT_SAMPLE_TARGET = 20.0
FULL_COVERAGE_FRACTION = 0.5
RECENCY_DECAY_DAYS = 21.0


@dataclass(frozen=True)
class TelemetryConfidence:
    """Computed route-level telemetry confidence and public source metadata."""

    confidence: float
    source: dict[str, object]


def _haversine_meters(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius_m = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    return radius_m * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def route_h3_cells(geometry: Dict[str, Any], resolution: int) -> list[str]:
    """Sample route geometry into unique H3 cells without inventing observations."""

    coordinates = flatten_geometry_coordinates(geometry)
    if len(coordinates) < 2:
        return []

    cells: list[str] = []
    seen: set[str] = set()

    def add_cell(lon: float, lat: float) -> None:
        cell = h3_latlng_to_cell(lat, lon, resolution)
        if cell not in seen:
            seen.add(cell)
            cells.append(cell)

    point_budget = MAX_ROUTE_SAMPLE_POINTS
    for start, end in zip(coordinates, coordinates[1:]):
        if len(start) < 2 or len(end) < 2:
            continue
        lon1, lat1 = float(start[0]), float(start[1])
        lon2, lat2 = float(end[0]), float(end[1])
        distance_m = _haversine_meters(lon1, lat1, lon2, lat2)
        steps = max(1, math.ceil(distance_m / ROUTE_SAMPLE_STEP_METERS))
        steps = min(steps, max(1, point_budget))
        for index in range(steps):
            fraction = index / steps
            add_cell(lon1 + (lon2 - lon1) * fraction, lat1 + (lat2 - lat1) * fraction)
        point_budget -= steps
        if point_budget <= 0:
            break
    last = coordinates[-1]
    if len(last) >= 2:
        add_cell(float(last[0]), float(last[1]))
    return cells


def _utc_datetime(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return parsed


def _count_score(sample_count: int) -> float:
    if sample_count <= 0:
        return 0.0
    return min(1.0, math.log1p(sample_count) / math.log1p(FULL_COUNT_SAMPLE_TARGET))


def _recency_score(last_seen_at: datetime | None, now: datetime) -> float:
    if last_seen_at is None:
        return 0.0
    age_days = max(0.0, (now - last_seen_at).total_seconds() / 86_400.0)
    return min(1.0, max(0.0, math.exp(-age_days / RECENCY_DECAY_DAYS)))


def _agreement_score(raw_stats: Mapping[str, Any] | None) -> float | None:
    if not raw_stats:
        return None
    raw_count = int(_float(raw_stats.get("raw_count"), 0.0))
    if raw_count <= 1:
        return None
    quality_stddev = _float(raw_stats.get("quality_stddev"), 0.0)
    return min(1.0, max(0.2, 1.0 - quality_stddev / 50.0))


def _weighted_score(scores: dict[str, float | None]) -> float:
    weights = {
        "count_score": 0.30,
        "recency_score": 0.25,
        "sensor_quality_score": 0.30,
        "agreement_score": 0.15,
    }
    total_weight = 0.0
    weighted_total = 0.0
    for key, weight in weights.items():
        value = scores.get(key)
        if value is None:
            continue
        total_weight += weight
        weighted_total += value * weight
    if total_weight <= 0:
        return 0.0
    return weighted_total / total_weight


def calculate_telemetry_confidence(
    route_cells: Iterable[str],
    aggregate_rows: Iterable[Mapping[str, Any]],
    raw_stats_by_cell: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    now: datetime | None = None,
) -> TelemetryConfidence | None:
    """Compute telemetry confidence from real aggregate/raw telemetry rows."""

    route_cell_list = list(dict.fromkeys(str(cell) for cell in route_cells if str(cell)))
    if not route_cell_list:
        return None
    raw_stats_by_cell = raw_stats_by_cell or {}
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    matched_cells = 0
    total_samples = 0
    weighted_confidence = 0.0
    latest_observation_at: datetime | None = None
    component_totals = {
        "count_score": 0.0,
        "recency_score": 0.0,
        "sensor_quality_score": 0.0,
        "agreement_score": 0.0,
    }
    component_weights = {key: 0.0 for key in component_totals}

    for row in aggregate_rows:
        h3_cell = str(row.get("h3_cell") or "")
        if h3_cell not in route_cell_list:
            continue
        sample_count = int(_float(row.get("sample_count"), 0.0))
        if sample_count <= 0:
            continue
        matched_cells += 1
        total_samples += sample_count
        sensor_quality = min(1.0, max(0.0, _float(row.get("confidence_sum"), 0.0) / sample_count))
        last_seen = _utc_datetime(row.get("last_seen_at"))
        if last_seen is not None and (latest_observation_at is None or last_seen > latest_observation_at):
            latest_observation_at = last_seen

        component_scores: dict[str, float | None] = {
            "count_score": _count_score(sample_count),
            "recency_score": _recency_score(last_seen, current_time),
            "sensor_quality_score": sensor_quality,
            "agreement_score": _agreement_score(raw_stats_by_cell.get(h3_cell)),
        }
        row_score = _weighted_score(component_scores)
        weighted_confidence += row_score * sample_count
        for key, value in component_scores.items():
            if value is None:
                continue
            component_totals[key] += value * sample_count
            component_weights[key] += sample_count

    if matched_cells == 0 or total_samples == 0:
        return None
    coverage_fraction = matched_cells / len(route_cell_list)
    if coverage_fraction < MIN_COVERAGE_FRACTION:
        return None
    coverage_modifier = min(1.0, coverage_fraction / FULL_COVERAGE_FRACTION)
    confidence = min(1.0, max(0.0, (weighted_confidence / total_samples) * coverage_modifier))
    component_scores = {
        key: round(component_totals[key] / component_weights[key], 3)
        for key in component_totals
        if component_weights[key] > 0
    }

    return TelemetryConfidence(
        confidence=round(confidence, 3),
        source={
            "active": True,
            "source": "sidewalk_telemetry",
            "mapping_method": "route_h3_cells",
            "sample_count": total_samples,
            "cell_count": matched_cells,
            "route_cell_count": len(route_cell_list),
            "coverage_fraction": round(coverage_fraction, 3),
            "avg_confidence": round(confidence, 3),
            "latest_observation_at": latest_observation_at.isoformat() if latest_observation_at else None,
            "formula": {
                "count_score": "log-scaled sample_count, full score at 20 samples/cell",
                "recency_score": "exponential decay from last_seen_at",
                "agreement_score": "raw quality-score consistency when raw samples exist",
                "sensor_quality_score": "aggregate confidence_sum / sample_count",
                "coverage": "confidence scaled by route H3 coverage",
            },
            "component_scores": component_scores,
        },
    )


def get_route_telemetry_confidence(geometry: Dict[str, Any]) -> TelemetryConfidence | None:
    """Return optional route telemetry confidence, or None when no real data exists."""

    settings = get_settings()
    resolution = settings.telemetry_default_h3_resolution
    route_cells = route_h3_cells(geometry, resolution)
    if not route_cells:
        return None
    started = datetime.now(timezone.utc)
    try:
        with get_engine().connect() as conn:
            aggregate_rows = (
                conn.execute(
                    text(
                        """
                        SELECT
                          h3_cell,
                          h3_resolution,
                          sample_count,
                          confidence_sum,
                          last_seen_at
                        FROM public.sidewalk_cell_aggregates
                        WHERE h3_resolution = :resolution
                          AND h3_cell = ANY(CAST(:cells AS text[]))
                        """
                    ),
                    {"resolution": resolution, "cells": route_cells},
                )
                .mappings()
                .all()
            )
            if not aggregate_rows:
                inc("saferoute_telemetry_confidence_total", {"status": "no_data"})
                return None
            raw_rows = (
                conn.execute(
                    text(
                        """
                        SELECT
                          h3_cell,
                          count(*) AS raw_count,
                          stddev_pop(quality_score) AS quality_stddev
                        FROM public.sidewalk_samples
                        WHERE h3_resolution = :resolution
                          AND h3_cell = ANY(CAST(:cells AS text[]))
                        GROUP BY h3_cell
                        """
                    ),
                    {"resolution": resolution, "cells": route_cells},
                )
                .mappings()
                .all()
            )
    except SQLAlchemyError:
        inc("saferoute_telemetry_confidence_total", {"status": "error"})
        return None

    aggregate_payload = [dict(row) for row in aggregate_rows]
    raw_by_cell = {str(row["h3_cell"]): dict(row) for row in raw_rows}
    result = calculate_telemetry_confidence(route_cells, aggregate_payload, raw_by_cell, now=started)
    status = "ok" if result is not None else "insufficient_coverage"
    inc("saferoute_telemetry_confidence_total", {"status": status})
    observe("saferoute_telemetry_confidence_route_cells", float(len(route_cells)), {"status": status})
    return result
