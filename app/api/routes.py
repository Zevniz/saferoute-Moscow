"""SafeRoute public HTTP API."""

from __future__ import annotations

from typing import Annotated, Any, List

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import get_engine
from app.core.metrics import render_prometheus
from app.core.security import protect_geocode, protect_health, protect_metrics, protect_route, protect_telemetry_write, protect_tiles
from app.schemas.routing import ErrorResponse, HealthResponse, ReverseResult, RouteMeta, RouteResponse, SearchResult
from app.schemas.telemetry import SidewalkCellCollection, SidewalkTelemetryBatch, TelemetryIngestResponse
from app.services.health import dependency_status
from app.services.routing import build_route_set
from app.services.scoring import RoutingMode, normalize_route_mode
from app.services.search import reverse_place, search_places
from app.services.telemetry import ingest_sidewalk_samples, list_sidewalk_cells

router = APIRouter()

Latitude = Annotated[float, Query(ge=-90.0, le=90.0)]
Longitude = Annotated[float, Query(ge=-180.0, le=180.0)]
TileZoom = Annotated[int, Path(ge=0, le=22)]
TileCoordinate = Annotated[int, Path(ge=0)]
RouteMode = Annotated[RoutingMode, Query(description="Route scoring mode.")]

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Запрошенные данные не найдены."},
    422: {"model": ErrorResponse, "description": "Некорректные параметры запроса."},
    503: {"model": ErrorResponse, "description": "Зависимость или база данных временно недоступна."},
}


@router.get(
    "/api/health",
    response_model=HealthResponse,
    responses=ERROR_RESPONSES,
    tags=["health"],
    summary="Check platform health",
)
def health(
    request: Request,
    deep: bool = Query(True, description="Check per-profile route readiness in addition to core dependencies."),
) -> HealthResponse:
    """Return dependency health and routing readiness."""

    protect_health(request, deep=deep)
    return dependency_status(deep=deep)


@router.get(
    "/api/metrics",
    tags=["observability"],
    summary="Expose Prometheus metrics",
    responses={
        200: {
            "description": "Prometheus text exposition for SafeRoute runtime metrics.",
            "content": {
                "text/plain": {
                    "example": '# HELP saferoute_http_requests_total HTTP requests handled by SafeRoute.\n# TYPE saferoute_http_requests_total counter\nsaferoute_http_requests_total{method="GET",path="/api/health",status="200"} 12'
                }
            },
        }
    },
)
def metrics(request: Request) -> Response:
    """Return local Prometheus metrics for the API gateway."""

    protect_metrics(request)
    return Response(content=render_prometheus(), media_type="text/plain; version=0.0.4; charset=utf-8")


@router.get(
    "/api/search",
    response_model=List[SearchResult],
    responses=ERROR_RESPONSES,
    tags=["geocoding"],
    summary="Search places in Moscow",
)
def search(request: Request, q: str = Query(..., min_length=2), limit: int = Query(5, ge=1, le=8)) -> List[SearchResult]:
    """Search for Moscow-biased places through Photon."""

    protect_geocode(request)
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="search query must contain at least 2 non-whitespace characters")
    return search_places(query, limit)


@router.get(
    "/api/reverse",
    response_model=ReverseResult,
    responses=ERROR_RESPONSES,
    tags=["geocoding"],
    summary="Reverse geocode one point",
)
def reverse(request: Request, lat: Latitude, lon: Longitude) -> ReverseResult:
    """Reverse geocode one coordinate pair."""

    protect_geocode(request)
    return reverse_place(lat, lon)


@router.get(
    "/api/route",
    response_model=RouteResponse,
    responses=ERROR_RESPONSES,
    tags=["routing"],
    summary="Build real route candidates",
)
def api_route(
    request: Request,
    lat1: Latitude,
    lon1: Longitude,
    lat2: Latitude,
    lon2: Longitude,
    profile: str = Query("walk", pattern="^(walk|bike|car)$"),
    mode: RouteMode = RoutingMode.SAFEST,
    alternatives: int = Query(3, ge=1, le=3),
) -> RouteResponse:
    """Build real route candidates for walk, bike, or car."""

    protect_route(request)
    mode_value = normalize_route_mode(mode).value
    try:
        routes = build_route_set(profile, lat1, lon1, lat2, lon2, alternatives, mode=mode_value)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Не удалось обогатить маршруты данными безопасности") from exc

    if not routes:
        raise HTTPException(status_code=404, detail="Маршрут не найден для выбранного режима")

    return RouteResponse(
        routes=routes,
        meta=RouteMeta(
            profile=profile,
            mode=mode_value,
            origin={"lat": lat1, "lon": lon1},
            destination={"lat": lat2, "lon": lon2},
        ),
    )


@router.get(
    "/route",
    response_model=RouteResponse,
    responses=ERROR_RESPONSES,
    tags=["compatibility"],
    summary="Compatibility alias for /api/route",
)
def legacy_route(
    request: Request,
    lat1: Latitude,
    lon1: Longitude,
    lat2: Latitude,
    lon2: Longitude,
    profile: str = Query("walk", pattern="^(walk|bike|car)$"),
    mode: RouteMode = RoutingMode.SAFEST,
    alternatives: int = Query(3, ge=1, le=3),
) -> RouteResponse:
    """Temporary compatibility alias for `/api/route`."""

    return api_route(request=request, lat1=lat1, lon1=lon1, lat2=lat2, lon2=lon2, profile=profile, mode=mode, alternatives=alternatives)


@router.post(
    "/api/telemetry/sidewalk-samples",
    response_model=TelemetryIngestResponse,
    responses=ERROR_RESPONSES,
    tags=["telemetry"],
    summary="Ingest sidewalk telemetry",
)
def sidewalk_samples(request: Request, batch: SidewalkTelemetryBatch) -> TelemetryIngestResponse:
    """Ingest sidewalk-quality telemetry from scooters, robots, and edge devices."""

    protect_telemetry_write(request)
    try:
        return ingest_sidewalk_samples(batch)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Телеметрия временно недоступна") from exc


@router.get(
    "/api/sidewalk-cells",
    response_model=SidewalkCellCollection,
    responses=ERROR_RESPONSES,
    tags=["telemetry"],
    summary="List aggregated sidewalk H3 cells",
)
def sidewalk_cells(
    request: Request,
    bbox: str = Query(..., description="minLon,minLat,maxLon,maxLat"),
    resolution: int = Query(9, ge=7, le=12),
) -> SidewalkCellCollection:
    """Return aggregated sidewalk-quality cells as GeoJSON."""

    protect_geocode(request)
    try:
        return list_sidewalk_cells(bbox=bbox, resolution=resolution)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Ячейки цифрового двойника временно недоступны") from exc


def validate_tile_coordinates(z: int, x: int, y: int) -> None:
    """Reject impossible XYZ tile coordinates before reaching PostGIS."""

    max_coordinate = (1 << z) - 1
    if x > max_coordinate or y > max_coordinate:
        raise HTTPException(status_code=422, detail="tile coordinates out of range for zoom")


@router.get("/tiles/{z}/{x}/{y}.pbf", include_in_schema=False)
def get_tile(request: Request, z: TileZoom, x: TileCoordinate, y: TileCoordinate) -> Response:
    """Return vector tiles for the safety graph."""

    protect_tiles(request)
    validate_tile_coordinates(z, x, y)
    query = text(
        """
        WITH bounds AS (SELECT ST_TileEnvelope(:z, :x, :y) AS geom),
        mvtgeom AS (
            SELECT ST_AsMVTGeom(ST_Transform(t.geometry, 3857), bounds.geom) AS geom
            FROM moscow_network t, bounds
            WHERE ST_Intersects(ST_Transform(t.geometry, 3857), bounds.geom)
        )
        SELECT ST_AsMVT(mvtgeom.*, 'roads') FROM mvtgeom;
        """
    )
    try:
        with get_engine().connect() as conn:
            result = conn.execute(query, {"z": z, "x": x, "y": y}).scalar()
            return Response(content=bytes(result or b""), media_type="application/x-protobuf")
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Тайлы временно недоступны") from exc
