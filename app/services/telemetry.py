"""Telemetry ingestion and sidewalk digital-twin aggregation."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import h3
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import get_engine
from app.schemas.telemetry import (
    SidewalkCellCollection,
    SidewalkCellFeature,
    SidewalkCellProperties,
    SidewalkSample,
    SidewalkTelemetryBatch,
    TelemetryIngestResponse,
)
from app.services.geometry import clamp

TELEMETRY_SCHEMA_SQL = Path(__file__).resolve().parents[2] / "docker" / "postgres" / "init" / "02_telemetry.sql"


def h3_latlng_to_cell(lat: float, lon: float, resolution: int) -> str:
    """Return an H3 cell across h3-py API versions."""

    if hasattr(h3, "latlng_to_cell"):
        return str(h3.latlng_to_cell(lat, lon, resolution))
    geo_to_h3 = getattr(h3, "geo_to_h3")
    return str(geo_to_h3(lat, lon, resolution))


def h3_cell_center(cell: str) -> Tuple[float, float]:
    """Return `(lat, lon)` center for an H3 cell."""

    if hasattr(h3, "cell_to_latlng"):
        lat, lon = h3.cell_to_latlng(cell)
        return float(lat), float(lon)
    h3_to_geo = getattr(h3, "h3_to_geo")
    lat, lon = h3_to_geo(cell)
    return float(lat), float(lon)


def h3_cell_polygon(cell: str) -> Dict[str, object]:
    """Return a GeoJSON polygon for an H3 cell."""

    if hasattr(h3, "cell_to_boundary"):
        boundary = h3.cell_to_boundary(cell)
        coordinates = [[float(lon), float(lat)] for lat, lon in boundary]
    else:
        h3_to_geo_boundary = getattr(h3, "h3_to_geo_boundary")
        boundary = h3_to_geo_boundary(cell, geo_json=True)
        coordinates = [[float(lon), float(lat)] for lon, lat in boundary]
    if coordinates and coordinates[0] != coordinates[-1]:
        coordinates.append(coordinates[0])
    return {"type": "Polygon", "coordinates": [coordinates]}


def ensure_telemetry_tables() -> None:
    """Create telemetry tables when they do not exist."""

    with get_engine().begin() as conn:
        for statement in telemetry_schema_statements():
            conn.execute(text(statement))


def telemetry_schema_statements() -> List[str]:
    """Return idempotent telemetry DDL statements shared with Docker init."""

    return [statement.strip() for statement in TELEMETRY_SCHEMA_SQL.read_text(encoding="utf-8").split(";") if statement.strip()]


def sample_quality(sample: SidewalkSample) -> Tuple[float, float, float, float]:
    """Compute normalized quality, confidence, obstacle, and vibration metrics."""

    base = sample.surface_score if sample.surface_score is not None else 100.0
    obstacle = sample.obstacle_score if sample.obstacle_score is not None else 0.0
    vibration = sample.vibration_rms if sample.vibration_rms is not None else 0.0
    gps_accuracy = sample.gps_accuracy_m if sample.gps_accuracy_m is not None else 12.0
    quality = clamp(base - obstacle * 35.0 - min(vibration * 4.0, 30.0) - min(gps_accuracy / 20.0 * 10.0, 15.0), 0.0, 100.0)
    confidence = clamp(1.0 - gps_accuracy / 50.0, 0.2, 1.0)
    return round(quality, 3), round(confidence, 3), round(obstacle, 3), round(vibration, 3)


def ingest_sidewalk_samples(batch: SidewalkTelemetryBatch) -> TelemetryIngestResponse:
    """Store raw sidewalk samples and update aggregate H3 cells."""

    settings = get_settings()
    if len(batch.samples) > settings.telemetry_max_batch_size:
        raise ValueError("too many telemetry samples")

    ensure_telemetry_tables()
    h3_resolution = telemetry_batch_resolution(batch)
    cells: set[Tuple[str, int]] = set()
    with get_engine().begin() as conn:
        for sample in batch.samples:
            cell = h3_latlng_to_cell(sample.lat, sample.lon, h3_resolution)
            centroid_lat, centroid_lon = h3_cell_center(cell)
            quality, confidence, obstacle, vibration = sample_quality(sample)
            cells.add((cell, h3_resolution))
            conn.execute(
                text(
                    """
                    INSERT INTO sidewalk_samples (
                        device_id, captured_at, lat, lon, speed_mps, source,
                        surface_score, vibration_rms, obstacle_score, gps_accuracy_m,
                        model_version, h3_cell, h3_resolution, quality_score, confidence
                    )
                    VALUES (
                        :device_id, :captured_at, :lat, :lon, :speed_mps, :source,
                        :surface_score, :vibration_rms, :obstacle_score, :gps_accuracy_m,
                        :model_version, :h3_cell, :h3_resolution, :quality_score, :confidence
                    )
                    """
                ),
                {
                    **sample.model_dump(),
                    "h3_cell": cell,
                    "h3_resolution": h3_resolution,
                    "quality_score": quality,
                    "confidence": confidence,
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO sidewalk_cell_aggregates (
                        h3_cell, h3_resolution, centroid_lat, centroid_lon, sample_count,
                        quality_sum, obstacle_sum, vibration_sum, confidence_sum,
                        first_seen_at, last_seen_at
                    )
                    VALUES (
                        :h3_cell, :h3_resolution, :centroid_lat, :centroid_lon, 1,
                        :quality_score, :obstacle_score, :vibration_rms, :confidence,
                        :captured_at, :captured_at
                    )
                    ON CONFLICT (h3_cell, h3_resolution)
                    DO UPDATE SET
                        sample_count = sidewalk_cell_aggregates.sample_count + 1,
                        quality_sum = sidewalk_cell_aggregates.quality_sum + EXCLUDED.quality_sum,
                        obstacle_sum = sidewalk_cell_aggregates.obstacle_sum + EXCLUDED.obstacle_sum,
                        vibration_sum = sidewalk_cell_aggregates.vibration_sum + EXCLUDED.vibration_sum,
                        confidence_sum = sidewalk_cell_aggregates.confidence_sum + EXCLUDED.confidence_sum,
                        first_seen_at = LEAST(sidewalk_cell_aggregates.first_seen_at, EXCLUDED.first_seen_at),
                        last_seen_at = GREATEST(sidewalk_cell_aggregates.last_seen_at, EXCLUDED.last_seen_at)
                    """
                ),
                {
                    "h3_cell": cell,
                    "h3_resolution": h3_resolution,
                    "centroid_lat": centroid_lat,
                    "centroid_lon": centroid_lon,
                    "quality_score": quality,
                    "obstacle_score": obstacle,
                    "vibration_rms": vibration,
                    "confidence": confidence,
                    "captured_at": sample.captured_at,
                },
            )
    return TelemetryIngestResponse(accepted=len(batch.samples), cells_updated=len(cells))


def telemetry_batch_resolution(batch: SidewalkTelemetryBatch) -> int:
    """Return explicit batch resolution or the configured runtime default."""

    if "h3_resolution" in batch.model_fields_set:
        return batch.h3_resolution
    return get_settings().telemetry_default_h3_resolution


def parse_bbox(bbox: str) -> Tuple[float, float, float, float]:
    """Parse bbox query string into `(minLon, minLat, maxLon, maxLat)`."""

    raw_parts = [item.strip() for item in bbox.split(",")]
    if len(raw_parts) != 4:
        raise ValueError("bbox must contain minLon,minLat,maxLon,maxLat")
    try:
        parts = [float(item) for item in raw_parts]
    except ValueError as exc:
        raise ValueError("bbox values must be numeric") from exc
    if not all(math.isfinite(value) for value in parts):
        raise ValueError("bbox values must be finite")
    min_lon, min_lat, max_lon, max_lat = parts
    if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180 and -90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise ValueError("bbox values must be valid longitude/latitude bounds")
    if min_lon >= max_lon or min_lat >= max_lat:
        raise ValueError("bbox min values must be smaller than max values")
    return min_lon, min_lat, max_lon, max_lat


def list_sidewalk_cells(bbox: str, resolution: int) -> SidewalkCellCollection:
    """Return aggregated sidewalk-quality H3 cells as GeoJSON."""

    min_lon, min_lat, max_lon, max_lat = parse_bbox(bbox)
    ensure_telemetry_tables()
    limit = get_settings().sidewalk_cells_limit
    query = text(
        """
        SELECT
            h3_cell, h3_resolution, sample_count, quality_sum, obstacle_sum,
            vibration_sum, confidence_sum, last_seen_at
        FROM sidewalk_cell_aggregates
        WHERE h3_resolution = :resolution
          AND centroid_lon BETWEEN :min_lon AND :max_lon
          AND centroid_lat BETWEEN :min_lat AND :max_lat
        ORDER BY last_seen_at DESC
        LIMIT :limit
        """
    )
    now = datetime.now(timezone.utc)
    features: List[SidewalkCellFeature] = []
    with get_engine().connect() as conn:
        rows = conn.execute(
            query,
            {
                "resolution": resolution,
                "min_lon": min_lon,
                "max_lon": max_lon,
                "min_lat": min_lat,
                "max_lat": max_lat,
                "limit": limit,
            },
        ).mappings()
        for row in rows:
            sample_count = max(1, int(row["sample_count"]))
            last_seen = row["last_seen_at"]
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            freshness_minutes = max(0.0, (now - last_seen).total_seconds() / 60.0)
            features.append(
                SidewalkCellFeature(
                    geometry=h3_cell_polygon(str(row["h3_cell"])),
                    properties=SidewalkCellProperties(
                        h3_cell=str(row["h3_cell"]),
                        h3_resolution=int(row["h3_resolution"]),
                        quality_score=round(float(row["quality_sum"]) / sample_count, 2),
                        sample_count=sample_count,
                        freshness_minutes=round(freshness_minutes, 2),
                        confidence=round(float(row["confidence_sum"]) / sample_count, 3),
                        obstacle_score=round(float(row["obstacle_sum"]) / sample_count, 3),
                        vibration_rms=round(float(row["vibration_sum"]) / sample_count, 3),
                    ),
                )
            )
    return SidewalkCellCollection(features=features)
