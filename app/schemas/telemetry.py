"""Telemetry schemas for sidewalk digital twin data."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


TelemetrySource = Literal["scooter", "robot", "mobile", "edge_camera", "manual"]


class SidewalkSample(BaseModel):
    """One observation from a device or edge inference pipeline."""

    model_config = ConfigDict(protected_namespaces=())

    device_id: str = Field(..., min_length=2, max_length=120)
    captured_at: datetime
    lat: float = Field(..., ge=55.0, le=56.5)
    lon: float = Field(..., ge=36.5, le=38.7)
    speed_mps: float = Field(..., ge=0, le=30)
    source: TelemetrySource
    surface_score: Optional[float] = Field(default=None, ge=0, le=100)
    vibration_rms: Optional[float] = Field(default=None, ge=0, le=20)
    obstacle_score: Optional[float] = Field(default=None, ge=0, le=1)
    gps_accuracy_m: Optional[float] = Field(default=None, ge=0, le=200)
    model_version: Optional[str] = Field(default=None, max_length=80)

    @field_validator("captured_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Require timezone-aware timestamps for telemetry ordering."""

        if value.tzinfo is None:
            raise ValueError("captured_at must include timezone")
        return value


class SidewalkTelemetryBatch(BaseModel):
    """Batch payload for sidewalk sample ingestion."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "samples": [
                    {
                        "device_id": "robot-17",
                        "captured_at": "2026-04-20T12:00:00Z",
                        "lat": 55.7558,
                        "lon": 37.6173,
                        "speed_mps": 1.1,
                        "source": "robot",
                        "surface_score": 93,
                        "vibration_rms": 1.7,
                        "obstacle_score": 0.12,
                        "gps_accuracy_m": 8,
                        "model_version": "edge-r3",
                    }
                ],
                "h3_resolution": 9,
            }
        }
    )

    samples: List[SidewalkSample] = Field(..., min_length=1, max_length=500)
    h3_resolution: int = Field(default=9, ge=7, le=12)


class TelemetryIngestResponse(BaseModel):
    """Telemetry ingest acknowledgement."""

    model_config = ConfigDict(json_schema_extra={"example": {"accepted": 12, "cells_updated": 4}})

    accepted: int
    cells_updated: int


class SidewalkCellProperties(BaseModel):
    """Aggregated digital-twin cell properties."""

    h3_cell: str
    h3_resolution: int
    quality_score: float
    sample_count: int
    freshness_minutes: float
    confidence: float
    obstacle_score: float
    vibration_rms: float


class SidewalkCellFeature(BaseModel):
    """GeoJSON feature for one sidewalk-quality cell."""

    type: str = "Feature"
    properties: SidewalkCellProperties
    geometry: Dict[str, Any]


class SidewalkCellCollection(BaseModel):
    """GeoJSON FeatureCollection for sidewalk-quality cells."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "h3_cell": "8911aa6b2b7ffff",
                            "h3_resolution": 9,
                            "quality_score": 84.6,
                            "sample_count": 18,
                            "freshness_minutes": 21.0,
                            "confidence": 0.81,
                            "obstacle_score": 0.16,
                            "vibration_rms": 2.1,
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[37.617, 55.756], [37.619, 55.755], [37.618, 55.753], [37.615, 55.753], [37.614, 55.755], [37.617, 55.756]]],
                        },
                    }
                ],
            }
        }
    )

    type: str = "FeatureCollection"
    features: List[SidewalkCellFeature]
