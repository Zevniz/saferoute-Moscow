"""Public routing, search, reverse, and health schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

RouteModeValue = Literal["safest", "fastest", "balanced", "accessible"]


class ErrorResponse(BaseModel):
    """Stable error envelope used in OpenAPI examples."""

    detail: str


class SearchResult(BaseModel):
    """A normalized Moscow-biased search result."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "landmark:moscow-kremlin",
                "label": "Московский Кремль, Москва",
                "lat": 55.7520233,
                "lon": 37.6174994,
                "bbox": [37.613, 55.747, 37.623, 55.7565],
                "kind": "landmark",
            }
        }
    )

    id: str
    label: str
    lat: float
    lon: float
    bbox: Optional[List[float]] = None
    kind: str = "place"


class ReverseResult(SearchResult):
    """Reverse geocoding result."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "reverse:55.7520:37.6175",
                "label": "Московский Кремль, Москва",
                "lat": 55.7520233,
                "lon": 37.6174994,
                "bbox": [37.613, 55.747, 37.623, 55.7565],
                "kind": "landmark",
                "source": "photon",
            }
        }
    )

    source: str = "photon"


class Instruction(BaseModel):
    """Valhalla maneuver normalized for the frontend navigation UI."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "index": 0,
                "text": "Двигайтесь прямо по улице Варварка",
                "distance_m": 220.0,
                "time_s": 140.0,
                "begin_shape_index": 0,
                "end_shape_index": 8,
                "type": 1,
                "street_names": ["Варварка"],
                "lanes": [],
            }
        }
    )

    index: int
    text: str
    distance_m: float
    time_s: float
    begin_shape_index: int
    end_shape_index: int
    type: Union[int, str]
    street_names: List[str] = Field(default_factory=list)
    lanes: List[Dict[str, Any]] = Field(default_factory=list)


class RouteScoreReason(BaseModel):
    """One explainable scoring reason based on real route attributes."""

    code: str
    impact: str
    message: str
    value: float
    weight: float


class RouteScoreDetails(BaseModel):
    """Detailed route score and factors used to calculate it."""

    mode: RouteModeValue
    total: int
    safety_index: int
    factors: Dict[str, Optional[float]]
    reasons: List[RouteScoreReason] = Field(default_factory=list)
    data_sources: Dict[str, Any] = Field(default_factory=dict)


class RouteProperties(BaseModel):
    """Route metadata used by cards, navigation, and safety UI."""

    distance_m: int
    estimated_mins: int
    safety_index: int
    profile: str
    variant: str
    mode: RouteModeValue = "safest"
    instructions: List[Instruction]
    bbox: Optional[List[float]] = None
    source: str
    navigable: bool = True
    score: Optional[RouteScoreDetails] = None


class RouteFeature(BaseModel):
    """GeoJSON Feature response for one route candidate."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "walk-safe",
                "label": "С более высокой оценкой",
                "subtitle": "Маршрут с приоритетом более спокойных пешеходных участков",
                "type": "Feature",
                "properties": {
                    "distance_m": 1830,
                    "estimated_mins": 23,
                    "safety_index": 88,
                    "profile": "walk",
                    "variant": "safe",
                    "mode": "safest",
                    "instructions": [
                        {
                            "index": 0,
                            "text": "Двигайтесь прямо по улице Варварка",
                            "distance_m": 220.0,
                            "time_s": 140.0,
                            "begin_shape_index": 0,
                            "end_shape_index": 8,
                            "type": 1,
                            "street_names": ["Варварка"],
                            "lanes": [],
                        }
                    ],
                    "bbox": [37.603, 55.7298, 37.6175, 55.752],
                    "source": "postgis+valhalla-trace",
                    "navigable": True,
                    "score": {
                        "mode": "safest",
                        "total": 90,
                        "safety_index": 90,
                        "factors": {
                            "avg_safety_weight": 1.4,
                            "min_width_m": 3.0,
                            "max_speed_kmh": 20.0,
                            "max_lanes": 2.0,
                            "track_fraction": 0.0,
                            "bike_lane_fraction": 0.0,
                            "walk_friendly_fraction": 0.72,
                        },
                        "reasons": [
                            {
                                "code": "walk_friendly_edges",
                                "impact": "positive",
                                "message": "A notable share of sampled route edges is footway or pedestrian.",
                                "value": 0.72,
                                "weight": 5.0,
                            }
                        ],
                    },
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[37.6174994, 55.7520233], [37.6112, 55.7442], [37.603033, 55.729804]],
                },
            }
        }
    )

    id: str
    label: str
    subtitle: str
    type: str = "Feature"
    properties: RouteProperties
    geometry: Dict[str, Any]


class RouteMeta(BaseModel):
    """Route response metadata."""

    profile: str
    mode: RouteModeValue = "safest"
    origin: Dict[str, float]
    destination: Dict[str, float]


class RouteResponse(BaseModel):
    """Collection of real route candidates."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "routes": [
                    {
                        "id": "walk-safe",
                        "label": "С более высокой оценкой",
                        "subtitle": "Маршрут с приоритетом более спокойных пешеходных участков",
                        "type": "Feature",
                        "properties": {
                            "distance_m": 1830,
                            "estimated_mins": 23,
                            "safety_index": 88,
                            "profile": "walk",
                            "variant": "safe",
                            "mode": "safest",
                            "instructions": [
                                {
                                    "index": 0,
                                    "text": "Двигайтесь прямо по улице Варварка",
                                    "distance_m": 220.0,
                                    "time_s": 140.0,
                                    "begin_shape_index": 0,
                                    "end_shape_index": 8,
                                    "type": 1,
                                    "street_names": ["Варварка"],
                                    "lanes": [],
                                }
                            ],
                            "bbox": [37.603, 55.7298, 37.6175, 55.752],
                            "source": "postgis+valhalla-trace",
                            "navigable": True,
                            "score": {
                                "mode": "safest",
                                "total": 90,
                                "safety_index": 90,
                                "factors": {
                                    "avg_safety_weight": 1.4,
                                    "min_width_m": 3.0,
                                    "max_speed_kmh": 20.0,
                                    "max_lanes": 2.0,
                                    "track_fraction": 0.0,
                                    "bike_lane_fraction": 0.0,
                                    "walk_friendly_fraction": 0.72,
                                },
                                "reasons": [
                                    {
                                        "code": "walk_friendly_edges",
                                        "impact": "positive",
                                        "message": "A notable share of sampled route edges is footway or pedestrian.",
                                        "value": 0.72,
                                        "weight": 5.0,
                                    }
                                ],
                            },
                        },
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[37.6174994, 55.7520233], [37.6112, 55.7442], [37.603033, 55.729804]],
                        },
                    }
                ],
                "meta": {
                    "profile": "walk",
                    "mode": "safest",
                    "origin": {"lat": 55.7520233, "lon": 37.6174994},
                    "destination": {"lat": 55.729804, "lon": 37.603033},
                },
            }
        }
    )

    routes: List[RouteFeature]
    meta: RouteMeta


class DependencyStatus(BaseModel):
    """Dependency health status."""

    status: str
    url: Optional[str] = None
    detail: Optional[str] = None
    latency_ms: Optional[float] = None


class ProfileReadiness(BaseModel):
    """Per-profile routing readiness from Valhalla."""

    status: str
    detail: Optional[str] = None
    latency_ms: Optional[float] = None


class HealthRuntime(BaseModel):
    """Runtime readiness metadata that clarifies production-like state."""

    environment: str = "development"
    public_fallback_allowed: bool = False
    production_like: bool = True
    readiness: Literal["self_hosted_ready", "local_dev_ready", "dev_fallback", "degraded", "unknown"] = "unknown"
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    """Health endpoint response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "services": {
                    "postgres": {
                        "status": "ok",
                        "url": "postgresql://saferoute:***@db:5432/saferoute_db",
                        "detail": None,
                        "latency_ms": 8.7,
                    },
                    "photon": {"status": "ok", "url": "http://photon:2322", "detail": None, "latency_ms": 72.4},
                    "valhalla": {"status": "ok", "url": "http://valhalla:8002", "detail": None, "latency_ms": 94.2},
                },
                "profiles": {
                    "walk": {"status": "ok", "detail": None, "latency_ms": 112.6},
                    "bike": {"status": "ok", "detail": None, "latency_ms": 118.1},
                    "car": {"status": "ok", "detail": None, "latency_ms": 109.3},
                },
                "runtime": {
                    "environment": "production",
                    "public_fallback_allowed": False,
                    "production_like": True,
                    "readiness": "self_hosted_ready",
                    "detail": "All checked dependencies are primary self-hosted services.",
                },
            }
        }
    )

    status: str
    services: Dict[str, DependencyStatus]
    profiles: Dict[str, ProfileReadiness] = Field(default_factory=dict)
    runtime: HealthRuntime = Field(default_factory=HealthRuntime)
