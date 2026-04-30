"""Route assembly service combining Valhalla and PostGIS safety data."""

from __future__ import annotations

import json
import math
import time
from collections import OrderedDict
from dataclasses import replace
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.metrics import inc, observe
from app.core.observability import log_event
from app.schemas.routing import Instruction, RouteFeature, RouteProperties, RouteScoreDetails
from app.services.geometry import (
    decode_polyline,
    flatten_geometry_coordinates,
    geometry_bounds,
    orient_geometry,
    sampling_line_geometry,
    simplify_coordinates,
)
from app.services.http import DependencyCallError, fetch_dependency_json
from app.services.scoring import (
    RouteAttributeSummary,
    RouteScoreResult,
    RoutingMode,
    calculate_route_score,
    calculate_safety_index,
    combined_filter_sql,
    cost_expression,
    normalize_route_mode,
    route_attribute_summary_sql,
)
from app.services.telemetry_confidence import get_route_telemetry_confidence
from app.services.weather import get_route_weather_risk

PROFILE_SPEEDS = {"walk": 4.8, "bike": 14.0, "car": 28.0}
VALHALLA_COSTING = {"walk": "pedestrian", "bike": "bicycle", "car": "auto"}
VARIANT_ORDER = ["safe", "balanced", "fast"]
VARIANT_LABELS = {
    "safe": "Наиболее безопасный",
    "balanced": "Сбалансированный",
    "fast": "Самый быстрый",
}
VARIANT_SUBTITLES = {
    "walk": {
        "safe": "Маршрут с приоритетом более спокойных пешеходных участков",
        "balanced": "Хороший компромисс между темпом и безопасностью",
        "fast": "Минимальное время в пути пешком",
    },
    "bike": {
        "safe": "Маршрут с приоритетом более спокойных улиц",
        "balanced": "Баланс скорости и дорожного комфорта",
        "fast": "Минимальное время на велосипеде",
    },
    "car": {
        "safe": "Маршрут с акцентом на более спокойную дорогу",
        "balanced": "Баланс скорости и дорожного комфорта",
        "fast": "Минимальное время за рулем",
    },
}
UNSCORED_SAFETY_INDEX = 50

PROFILE_FILTERS = {
    "walk": """
        NOT (
            LOWER(COALESCE(highway, '')) LIKE '%%motorway%%'
            OR LOWER(COALESCE(highway, '')) LIKE '%%trunk%%'
        )
    """,
    "bike": "LOWER(COALESCE(highway, '')) NOT LIKE '%%steps%%'",
    "car": """
        LOWER(COALESCE(highway, '')) NOT LIKE '%%footway%%'
        AND LOWER(COALESCE(highway, '')) NOT LIKE '%%path%%'
        AND LOWER(COALESCE(highway, '')) NOT LIKE '%%steps%%'
        AND LOWER(COALESCE(highway, '')) NOT LIKE '%%pedestrian%%'
        AND LOWER(COALESCE(highway, '')) NOT LIKE '%%track%%'
        AND LOWER(COALESCE(highway, '')) NOT LIKE '%%cycleway%%'
    """,
}
PROFILE_FILTER_CANDIDATES = {
    "walk": [PROFILE_FILTERS["walk"]],
    "bike": [PROFILE_FILTERS["bike"]],
    "car": [PROFILE_FILTERS["car"], "LOWER(COALESCE(highway, '')) NOT LIKE '%%steps%%'"],
}
_ROUTE_CACHE: OrderedDict[Tuple[Any, ...], Tuple[float, List[RouteFeature]]] = OrderedDict()
_NETWORK_COLUMNS: Optional[set[str]] = None
_METADATA_CACHE_TTL_SECONDS = 30.0
_ENRICHMENT_COLUMNS_CACHE: Tuple[float, set[str]] | None = None
_ACTIVE_ENRICHMENT_VERSION_CACHE: Tuple[float, str] | None = None
_ACTIVE_ENRICHMENT_PUBLIC_METADATA_CACHE: Tuple[float, dict[str, object]] | None = None
_MATERIALIZED_NODES_CACHE: Tuple[float, bool] | None = None

BASE_SCORING_COLUMNS = ("id", "highway", "safety_weight", "width", "est_width", "maxspeed", "lanes", "access")
ENRICHMENT_SCORING_COLUMNS = (
    "surface_type",
    "surface_quality",
    "sidewalk_presence",
    "sidewalk_width_m",
    "curb_risk",
    "curb_frequency",
    "curb_density_per_km",
    "crossing_count",
    "controlled_crossing_count",
    "uncontrolled_crossing_count",
    "crossing_risk",
    "lighting_quality",
    "slope_percent",
    "traffic_intensity",
    "pedestrian_density",
    "micromobility_allowed",
    "forbidden_zone",
    "micromobility_slow_zone",
    "zone_speed_limit_kmh",
    "road_exposure_proxy",
    "weather_sensitive_risk",
    "enrichment_confidence",
    "telemetry_confidence",
)


def clear_route_metadata_caches() -> None:
    """Clear short-lived route metadata caches, mainly for tests and import flows."""

    global _ENRICHMENT_COLUMNS_CACHE
    global _ACTIVE_ENRICHMENT_VERSION_CACHE
    global _ACTIVE_ENRICHMENT_PUBLIC_METADATA_CACHE
    global _MATERIALIZED_NODES_CACHE
    _ENRICHMENT_COLUMNS_CACHE = None
    _ACTIVE_ENRICHMENT_VERSION_CACHE = None
    _ACTIVE_ENRICHMENT_PUBLIC_METADATA_CACHE = None
    _MATERIALIZED_NODES_CACHE = None


def _ttl_cache_valid(item: tuple[float, object] | None) -> bool:
    """Return whether a simple `(expires_at, value)` cache item is still usable."""

    return item is not None and item[0] >= time.time()


def estimate_minutes(distance_meters: float, profile: str) -> int:
    """Estimate minutes using fixed MVP profile speeds."""

    speed_kmh = PROFILE_SPEEDS[profile]
    return max(1, round((distance_meters / 1000.0) / speed_kmh * 60.0))


def encode_query_json(payload: Dict[str, Any]) -> str:
    """Serialize Valhalla request JSON for GET endpoints."""

    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def get_network_columns() -> set[str]:
    """Return available columns on `moscow_network`, cached per process."""

    global _NETWORK_COLUMNS
    if _NETWORK_COLUMNS is not None:
        return _NETWORK_COLUMNS

    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'moscow_network'
                """
            )
        )
        _NETWORK_COLUMNS = {str(row[0]) for row in rows}
    return _NETWORK_COLUMNS


def get_enrichment_columns() -> set[str]:
    """Return enrichment columns only when a real active dataset is present."""

    global _ENRICHMENT_COLUMNS_CACHE
    cached_columns = _ENRICHMENT_COLUMNS_CACHE
    if cached_columns is not None and _ttl_cache_valid(cached_columns):
        return set(cached_columns[1])

    with get_engine().connect() as conn:
        active_count = conn.execute(
            text(
                """
                SELECT count(*)
                FROM public.safety_enrichment_datasets
                WHERE is_active = true
                """
            )
        ).scalar_one_or_none()
        if not active_count:
            return set()

        rows = conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'safety_edge_enrichment'
                """
            )
        )
        columns = {str(row[0]) for row in rows}
    _ENRICHMENT_COLUMNS_CACHE = (time.time() + _METADATA_CACHE_TTL_SECONDS, columns)
    return set(columns)


def get_active_enrichment_version() -> str:
    """Return the active enrichment version for route-cache invalidation."""

    global _ACTIVE_ENRICHMENT_VERSION_CACHE
    cached_version = _ACTIVE_ENRICHMENT_VERSION_CACHE
    if cached_version is not None and _ttl_cache_valid(cached_version):
        return str(cached_version[1])

    try:
        with get_engine().connect() as conn:
            active_version = conn.execute(
                text(
                    """
                    SELECT COALESCE(string_agg(dataset_version, ',' ORDER BY dataset_version), 'none')
                    FROM public.safety_enrichment_datasets
                    WHERE is_active = true
                    """
                )
            ).scalar_one()
    except SQLAlchemyError:
        return "unavailable"
    version = str(active_version)
    _ACTIVE_ENRICHMENT_VERSION_CACHE = (time.time() + _METADATA_CACHE_TTL_SECONDS, version)
    return version


def get_active_enrichment_public_metadata() -> dict[str, object]:
    """Return API-safe metadata about all active enrichment datasets."""

    global _ACTIVE_ENRICHMENT_PUBLIC_METADATA_CACHE
    cached_metadata = _ACTIVE_ENRICHMENT_PUBLIC_METADATA_CACHE
    if cached_metadata is not None and _ttl_cache_valid(cached_metadata):
        return dict(cached_metadata[1])

    try:
        with get_engine().connect() as conn:
            rows = (
                conn.execute(
                    text(
                        """
                        SELECT dataset_version, source_name, source_url, metadata
                        FROM public.safety_enrichment_datasets
                        WHERE is_active = true
                        ORDER BY imported_at DESC
                        """
                    )
                )
                .mappings()
                .all()
            )
    except SQLAlchemyError:
        metadata = {"active": False, "active_factors": [], "status": "unavailable"}
        _ACTIVE_ENRICHMENT_PUBLIC_METADATA_CACHE = (time.time() + _METADATA_CACHE_TTL_SECONDS, metadata)
        return dict(metadata)
    if not rows:
        metadata = {"active": False, "active_factors": []}
        _ACTIVE_ENRICHMENT_PUBLIC_METADATA_CACHE = (time.time() + _METADATA_CACHE_TTL_SECONDS, metadata)
        return dict(metadata)
    datasets: list[dict[str, object]] = []
    active_factor_set: set[str] = set()
    weighted_confidence_total = 0.0
    confidence_weight_count = 0
    for row in rows:
        raw_metadata = row.get("metadata")
        metadata: dict[str, object] = raw_metadata if isinstance(raw_metadata, dict) else {}
        raw_factor_counts = metadata.get("factor_counts")
        factor_counts: dict[str, object] = raw_factor_counts if isinstance(raw_factor_counts, dict) else {}
        active_factors = sorted(factor for factor, count in factor_counts.items() if count)
        active_factor_set.update(active_factors)
        avg_confidence = metadata.get("avg_confidence")
        if isinstance(avg_confidence, (int, float)):
            weighted_confidence_total += float(avg_confidence)
            confidence_weight_count += 1
        datasets.append(
            {
                "dataset_version": row["dataset_version"],
                "source_name": row["source_name"],
                "source_url": row["source_url"],
                "license": metadata.get("license"),
                "mapping_method": metadata.get("mapping_method"),
                "latest_osm_timestamp": metadata.get("latest_osm_timestamp"),
                "avg_confidence": avg_confidence,
                "active_factors": active_factors,
            }
        )
    primary = datasets[0]
    avg_confidence = round(weighted_confidence_total / confidence_weight_count, 3) if confidence_weight_count else None
    metadata = {
        "active": True,
        "dataset_version": primary.get("dataset_version"),
        "source_name": primary.get("source_name"),
        "source_url": primary.get("source_url"),
        "license": primary.get("license"),
        "mapping_method": primary.get("mapping_method"),
        "latest_osm_timestamp": primary.get("latest_osm_timestamp"),
        "avg_confidence": avg_confidence,
        "active_factors": sorted(active_factor_set),
        "datasets": datasets,
        "dataset_versions": [dataset["dataset_version"] for dataset in datasets],
    }
    _ACTIVE_ENRICHMENT_PUBLIC_METADATA_CACHE = (time.time() + _METADATA_CACHE_TTL_SECONDS, metadata)
    return dict(metadata)


def _projection_source_expression(column: str, graph_columns: set[str], enrichment_columns: set[str]) -> str | None:
    """Build a real-data projection expression for one scoring column."""

    expressions: list[str] = []
    if column == "enrichment_confidence" and "confidence" in enrichment_columns:
        expressions.append("(enrichment.confidence)::TEXT")
    if column in enrichment_columns:
        expressions.append(f"(enrichment.{column})::TEXT")
    if column in graph_columns:
        expressions.append(f"(edge.{column})::TEXT")
    if column == "surface_type" and "surface" in graph_columns:
        expressions.append("(edge.surface)::TEXT")
    if column == "sidewalk_width_m" and "sidewalk_width" in graph_columns:
        expressions.append("(edge.sidewalk_width)::TEXT")
    if column == "slope_percent" and "incline" in graph_columns:
        expressions.append("(edge.incline)::TEXT")
    if not expressions:
        return None
    return f"COALESCE({', '.join(expressions)}) AS {column}"


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the direct geodesic distance between two WGS84 points."""

    radius_meters = 6_371_000.0
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat / 2.0) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2.0) ** 2
    return radius_meters * 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def safe_corridor_margin_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the configured routing corridor margin for one point pair."""

    settings = get_settings()
    direct_meters = haversine_meters(lat1, lon1, lat2, lon2)
    dynamic_margin = direct_meters * settings.route_safe_corridor_direct_distance_ratio
    return min(
        float(settings.route_safe_corridor_max_meters),
        max(float(settings.route_safe_corridor_min_meters), dynamic_margin),
    )


def safe_corridor_bounds(lat1: float, lon1: float, lat2: float, lon2: float, margin_meters: float) -> tuple[float, float, float, float]:
    """Return a WGS84 bbox expanded by a meter margin around the direct route envelope."""

    center_lat = (lat1 + lat2) / 2.0
    meters_per_lat_degree = 111_320.0
    meters_per_lon_degree = max(32_000.0, meters_per_lat_degree * math.cos(math.radians(center_lat)))
    lat_delta = margin_meters / meters_per_lat_degree
    lon_delta = margin_meters / meters_per_lon_degree
    min_lon = max(-180.0, min(lon1, lon2) - lon_delta)
    min_lat = max(-90.0, min(lat1, lat2) - lat_delta)
    max_lon = min(180.0, max(lon1, lon2) + lon_delta)
    max_lat = min(90.0, max(lat1, lat2) + lat_delta)
    return (min_lon, min_lat, max_lon, max_lat)


def safe_corridor_filter_sql(lat1: float, lon1: float, lat2: float, lon2: float) -> str | None:
    """Return a geometry bbox predicate for bounded pgRouting, or None when disabled."""

    settings = get_settings()
    if not settings.route_safe_corridor_enabled:
        return None
    margin_meters = safe_corridor_margin_meters(lat1, lon1, lat2, lon2)
    min_lon, min_lat, max_lon, max_lat = safe_corridor_bounds(lat1, lon1, lat2, lon2, margin_meters)
    return (
        "geometry && "
        f"ST_MakeEnvelope({min_lon:.8f}, {min_lat:.8f}, {max_lon:.8f}, {max_lat:.8f}, 4326)"
    )


def route_strategy_signature() -> tuple[object, ...]:
    """Return settings that materially affect route geometry and cache validity."""

    settings = get_settings()
    return (
        settings.route_graph_algorithm.lower(),
        bool(settings.route_safe_corridor_enabled),
        int(settings.route_safe_corridor_min_meters),
        round(float(settings.route_safe_corridor_direct_distance_ratio), 4),
        int(settings.route_safe_corridor_max_meters),
        bool(settings.route_safe_corridor_fallback_enabled),
    )


def scoring_edges_cte_sql(graph_columns: set[str], enrichment_columns: set[str]) -> tuple[str, set[str]]:
    """Return the nearest-edge CTE that overlays real active enrichment rows."""

    projected_columns: set[str] = set()
    projections: list[str] = []
    for column in BASE_SCORING_COLUMNS:
        if column in graph_columns:
            projections.append(f"edge.{column} AS {column}")
            projected_columns.add(column)
    for column in ENRICHMENT_SCORING_COLUMNS:
        expression = _projection_source_expression(column, graph_columns, enrichment_columns)
        if expression is not None:
            projections.append(expression)
            projected_columns.add(column)

    enrichment_join = ""
    if enrichment_columns:
        merged_columns: list[str] = ["MAX(enrichment.confidence) AS confidence"]
        for column in ENRICHMENT_SCORING_COLUMNS:
            if column == "enrichment_confidence" or column not in enrichment_columns:
                continue
            merged_columns.append(
                f"""
                (array_agg(enrichment.{column}
                  ORDER BY enrichment.confidence DESC NULLS LAST, enrichment.observed_at DESC NULLS LAST)
                  FILTER (WHERE enrichment.{column} IS NOT NULL))[1] AS {column}
                """.strip()
            )
        enrichment_join = """
            LEFT JOIN LATERAL (
                SELECT {merged_columns}
                FROM safety_edge_enrichment AS enrichment
                JOIN safety_enrichment_datasets AS dataset
                  ON dataset.dataset_version = enrichment.dataset_version
                WHERE enrichment.edge_id = edge.id
                  AND dataset.is_active = true
            ) AS enrichment ON true
        """.format(merged_columns=", ".join(merged_columns))

    if not projections:
        projections = ["edge.id AS id"]
        projected_columns.add("id")

    return (
        f"""
        nearest_edges AS (
            SELECT {", ".join(projections)}
            FROM sample_points
            CROSS JOIN LATERAL (
                SELECT *
                FROM moscow_network
                ORDER BY geometry <-> sample_points.point
                LIMIT 1
            ) AS edge
            {enrichment_join}
        )
        """,
        projected_columns,
    )


def route_cache_key(profile: str, lat1: float, lon1: float, lat2: float, lon2: float, alternatives: int, mode: str | RoutingMode) -> Tuple[Any, ...]:
    """Build a normalized in-memory route cache key."""

    precision = get_settings().route_bucket_precision
    return (
        get_settings().route_data_version,
        get_active_enrichment_version(),
        route_strategy_signature(),
        profile,
        normalize_route_mode(mode).value,
        round(lat1, precision),
        round(lon1, precision),
        round(lat2, precision),
        round(lon2, precision),
        alternatives,
    )


def cache_get(key: Tuple[Any, ...]) -> Optional[List[RouteFeature]]:
    """Return unexpired cached routes."""

    item = _ROUTE_CACHE.get(key)
    if not item:
        inc("saferoute_route_cache_total", {"result": "miss"})
        return None
    expires_at, routes = item
    if expires_at < time.time():
        _ROUTE_CACHE.pop(key, None)
        inc("saferoute_route_cache_total", {"result": "expired"})
        return None
    _ROUTE_CACHE.move_to_end(key)
    inc("saferoute_route_cache_total", {"result": "hit"})
    return routes


def cache_set(key: Tuple[Any, ...], routes: List[RouteFeature]) -> None:
    """Cache route candidates for repeated nearby requests."""

    settings = get_settings()
    ttl = settings.route_cache_ttl_seconds
    _ROUTE_CACHE[key] = (time.time() + ttl, routes)
    _ROUTE_CACHE.move_to_end(key)
    while len(_ROUTE_CACHE) > settings.route_cache_max_entries:
        _ROUTE_CACHE.popitem(last=False)


def normalize_instruction(index: int, maneuver: Dict[str, Any]) -> Optional[Instruction]:
    """Convert one Valhalla maneuver to the SafeRoute instruction schema."""

    text = maneuver.get("instruction")
    if not isinstance(text, str) or not text.strip():
        return None

    maneuver_type = maneuver.get("type")

    return Instruction(
        index=index,
        text=text.strip(),
        distance_m=round(float(maneuver.get("length") or 0.0) * 1000.0, 1),
        time_s=round(float(maneuver.get("time") or 0.0), 3),
        begin_shape_index=int(maneuver.get("begin_shape_index") or 0),
        end_shape_index=int(maneuver.get("end_shape_index") or maneuver.get("begin_shape_index") or 0),
        type=maneuver_type if maneuver_type is not None else "continue",
        street_names=[str(name) for name in (maneuver.get("street_names") or []) if name],
        lanes=maneuver.get("lanes") or [],
    )


def summary_bbox(summary: Dict[str, Any], fallback_geometry: Dict[str, Any]) -> Optional[List[float]]:
    """Return Valhalla summary bbox when complete, otherwise derive it from geometry."""

    values = [summary.get(key) for key in ("min_lon", "min_lat", "max_lon", "max_lat")]
    if any(value is None for value in values):
        return geometry_bounds(fallback_geometry)
    return [float(value) for value in values if value is not None]


def normalize_trip_route(trip: Dict[str, Any], *, source: str, profile: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Normalize one Valhalla trip object into internal route data."""

    legs = trip.get("legs") or []
    if not legs:
        return None

    leg = legs[0]
    shape = leg.get("shape")
    if not shape:
        return None

    instructions: List[Instruction] = []
    for maneuver in leg.get("maneuvers") or []:
        instruction = normalize_instruction(len(instructions), maneuver)
        if instruction is not None:
            instructions.append(instruction)
    if not instructions:
        return None

    geometry = {"type": "LineString", "coordinates": decode_polyline(shape, precision=6)}
    summary = leg.get("summary") or trip.get("summary") or {}
    distance_m = round(float(summary.get("length") or 0.0) * 1000.0)
    time_seconds = float(summary.get("time") or 0.0)
    estimated_mins = estimate_minutes(distance_m, profile) if profile else max(1, round(time_seconds / 60.0))
    return {
        "geometry": geometry,
        "distance_m": distance_m,
        "estimated_mins": estimated_mins if time_seconds or profile else 0,
        "instructions": instructions,
        "bbox": summary_bbox(summary, geometry),
        "source": source,
    }


def apply_unscored_safety_fallback(routes: List[Dict[str, Any]], profile: str, mode: str | RoutingMode, reason: str) -> None:
    """Keep navigable Valhalla routes when the safety graph is unavailable."""

    mode_value = normalize_route_mode(mode).value
    for route in routes:
        route["safety_index"] = UNSCORED_SAFETY_INDEX
        route.pop("score", None)
        source = str(route.get("source") or "valhalla")
        if "unscored" not in source:
            route["source"] = f"{source}+unscored"

    inc("saferoute_route_failures_total", {"profile": profile, "reason": "safety_enrichment_unavailable"})
    log_event("route_safety_fallback", profile=profile, mode=mode_value, routes=len(routes), reason=reason)


def build_route_request(profile: str, lat1: float, lon1: float, lat2: float, lon2: float, alternates: int) -> Dict[str, Any]:
    """Build a Valhalla route request with Russian maneuvers enabled."""

    return {
        "locations": [{"lat": lat1, "lon": lon1}, {"lat": lat2, "lon": lon2}],
        "costing": VALHALLA_COSTING[profile],
        "directions_options": {"language": "ru-RU", "units": "kilometers"},
        "alternates": max(0, alternates - 1),
    }


def fetch_valhalla_routes(profile: str, lat1: float, lon1: float, lat2: float, lon2: float, alternatives: int) -> List[Dict[str, Any]]:
    """Fetch ordinary Valhalla route candidates."""

    payload = build_route_request(profile, lat1, lon1, lat2, lon2, alternatives)
    try:
        response, latency_ms, source_url = fetch_dependency_json(
            "valhalla",
            "GET",
            "/route",
            params={"json": encode_query_json(payload)},
        )
    except DependencyCallError as exc:
        raise HTTPException(status_code=503, detail="Сервис turn-by-turn маршрутов временно недоступен") from exc

    source = "valhalla-public-fallback" if "openstreetmap.de" in source_url else "valhalla"
    normalized: List[Dict[str, Any]] = []
    seen_shapes: set[str] = set()
    for item in [response] + (response.get("alternates") or []):
        route = normalize_trip_route(item.get("trip") or {}, source=source, profile=profile)
        if route is None:
            continue
        shape_key = json.dumps(route["geometry"], separators=(",", ":"))
        if shape_key in seen_shapes:
            continue
        seen_shapes.add(shape_key)
        normalized.append(route)

    log_event("valhalla_routes", profile=profile, count=len(normalized), latency_ms=latency_ms, source=source)
    return normalized


def build_edge_sql(profile: str, filter_sql: str, mode: str | RoutingMode) -> str:
    """Build pgRouting edge SQL for the active safety profile."""

    columns = get_network_columns()
    astar_columns = {"source_x", "source_y", "target_x", "target_y"}
    astar_projection = ""
    if astar_columns.issubset(columns):
        astar_projection = """
            ,
            source_x AS x1,
            source_y AS y1,
            target_x AS x2,
            target_y AS y2
        """

    route_sql = f"""
        SELECT
            id,
            u AS source,
            v AS target,
            {cost_expression(profile, mode, columns)} AS cost,
            {cost_expression(profile, mode, columns)} AS reverse_cost
            {astar_projection}
        FROM moscow_network
        WHERE {filter_sql}
    """
    return " ".join(route_sql.split())


def use_materialized_nodes() -> bool:
    """Return whether the optional routing support node table exists."""

    global _MATERIALIZED_NODES_CACHE
    cached_materialized_nodes = _MATERIALIZED_NODES_CACHE
    if cached_materialized_nodes is not None and _ttl_cache_valid(cached_materialized_nodes):
        return bool(cached_materialized_nodes[1])

    with get_engine().connect() as conn:
        exists = conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public'
                      AND c.relname = 'moscow_network_nodes'
                      AND c.relkind IN ('r', 'm', 'v')
                )
                """
            )
        ).scalar()
    result = bool(exists)
    _MATERIALIZED_NODES_CACHE = (time.time() + _METADATA_CACHE_TTL_SECONDS, result)
    return result


def node_cte_sql(filter_sql: str, node_filter_sql: str | None = None) -> str:
    """Build nearest-node CTE source using materialized nodes when available."""

    if use_materialized_nodes():
        where_sql = ""
        if node_filter_sql:
            where_sql = f"WHERE {node_filter_sql.replace('geometry', 'nodes.geometry', 1)}"
        return f"""
            SELECT eligible.node_id, nodes.geometry AS node_geometry
            FROM (
                SELECT u AS node_id
                FROM moscow_network
                WHERE {filter_sql}
                UNION
                SELECT v AS node_id
                FROM moscow_network
                WHERE {filter_sql}
            ) AS eligible
            JOIN moscow_network_nodes AS nodes
              ON nodes.node_id = eligible.node_id
            {where_sql}
        """
    return f"""
        SELECT
            u AS node_id,
            ST_StartPoint(ST_GeometryN(geometry, 1)) AS node_geometry
        FROM moscow_network
        WHERE {filter_sql}
        UNION ALL
        SELECT
            v AS node_id,
            ST_EndPoint(ST_GeometryN(geometry, ST_NumGeometries(geometry))) AS node_geometry
        FROM moscow_network
        WHERE {filter_sql}
    """


def should_use_astar() -> bool:
    """Return whether the prepared graph can use pgr_aStar."""

    settings = get_settings()
    return settings.route_graph_algorithm.lower() == "astar" and {
        "source_x",
        "source_y",
        "target_x",
        "target_y",
    }.issubset(get_network_columns())


def build_safe_route_query(
    profile: str,
    filter_sql: str,
    mode: str | RoutingMode = "safest",
    algorithm: str = "astar",
    corridor_filter_sql: str | None = None,
) -> str:
    """Build pgRouting SQL for the safety-first route."""

    filter_sql = " ".join(combined_filter_sql(profile, filter_sql, mode, get_network_columns()).split())
    effective_filter_sql = filter_sql
    if corridor_filter_sql:
        effective_filter_sql = f"({filter_sql}) AND ({corridor_filter_sql})"
    route_sql = build_edge_sql(profile, effective_filter_sql, mode).replace("'", "''")
    node_source_sql = node_cte_sql(effective_filter_sql, node_filter_sql=corridor_filter_sql)
    routing_function = "pgr_aStar" if algorithm == "astar" else "pgr_dijkstra"
    return f"""
        WITH start_node AS (
            SELECT node_id
            FROM ({node_source_sql}) AS start_candidates
            ORDER BY node_geometry <-> ST_SetSRID(ST_MakePoint(:lon1, :lat1), 4326)
            LIMIT 1
        ),
        end_node AS (
            SELECT node_id
            FROM ({node_source_sql}) AS end_candidates
            ORDER BY node_geometry <-> ST_SetSRID(ST_MakePoint(:lon2, :lat2), 4326)
            LIMIT 1
        ),
        route AS (
            SELECT *
            FROM {routing_function}(
                '{route_sql}',
                (SELECT node_id FROM start_node),
                (SELECT node_id FROM end_node),
                false
            )
        )
        SELECT
            ST_AsGeoJSON(ST_LineMerge(ST_Union(m.geometry))) AS geometry,
            SUM(m.length) AS distance_meters
        FROM route r
        JOIN moscow_network m ON r.edge = m.id
    """


def _safe_geometry_suspicious(distance_meters: float, direct_meters: float) -> bool:
    """Return whether a bounded safe route is implausibly long and should fallback."""

    if direct_meters <= 0:
        return False
    return distance_meters > max(direct_meters * 4.5, direct_meters + 12_000.0)


def _fetch_safe_geometry_scope(
    conn: Any,
    profile: str,
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    *,
    mode: str,
    scope: str,
    corridor_filter_sql: str | None,
) -> tuple[Optional[Dict[str, Any]], str | None]:
    """Fetch one safe geometry using either full or bounded graph SQL."""

    started = time.perf_counter()
    empty_geometry_seen = False
    for filter_sql in PROFILE_FILTER_CANDIDATES[profile]:
        algorithms = ["astar", "dijkstra"] if should_use_astar() else ["dijkstra"]
        row = None
        used_algorithm = algorithms[0]
        for algorithm in algorithms:
            try:
                row = conn.execute(
                    text(build_safe_route_query(profile, filter_sql, mode=mode, algorithm=algorithm, corridor_filter_sql=corridor_filter_sql)),
                    {"lat1": lat1, "lon1": lon1, "lat2": lat2, "lon2": lon2},
                ).mappings().one()
                used_algorithm = algorithm
                break
            except SQLAlchemyError as exc:
                if algorithm == algorithms[-1]:
                    raise
                log_event(
                    "safe_geometry_algorithm_fallback",
                    profile=profile,
                    mode=mode,
                    scope=scope,
                    from_algorithm=algorithm,
                    reason=exc.__class__.__name__,
                )
                inc("saferoute_route_failures_total", {"profile": profile, "reason": f"{algorithm}_failed"})
        if row is None:
            continue
        geometry_json = row.get("geometry")
        if not geometry_json or not row.get("distance_meters"):
            empty_geometry_seen = True
            continue
        geometry = json.loads(geometry_json) if isinstance(geometry_json, str) else geometry_json
        geometry = orient_geometry(geometry, lat1, lon1, lat2, lon2)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        observe(
            "saferoute_safe_geometry_duration_ms",
            duration_ms,
            {"profile": profile, "mode": mode, "algorithm": used_algorithm, "scope": scope},
        )
        log_event("safe_geometry", profile=profile, mode=mode, algorithm=used_algorithm, scope=scope, duration_ms=duration_ms)
        return {"geometry": geometry, "distance_m": round(float(row["distance_meters"]))}, None
    return None, "empty_geometry" if empty_geometry_seen else "no_route"


def fetch_safe_geometry(profile: str, lat1: float, lon1: float, lat2: float, lon2: float, *, mode: str | RoutingMode) -> Optional[Dict[str, Any]]:
    """Fetch a safety-first geometry from PostGIS/pgRouting."""

    mode_value = normalize_route_mode(mode).value
    settings = get_settings()
    direct_meters = haversine_meters(lat1, lon1, lat2, lon2)
    corridor_filter = safe_corridor_filter_sql(lat1, lon1, lat2, lon2)
    with get_engine().connect() as conn:
        if corridor_filter:
            try:
                bounded_result, bounded_reason = _fetch_safe_geometry_scope(
                    conn,
                    profile,
                    lat1,
                    lon1,
                    lat2,
                    lon2,
                    mode=mode_value,
                    scope="bounded",
                    corridor_filter_sql=corridor_filter,
                )
            except SQLAlchemyError as exc:
                if not settings.route_safe_corridor_fallback_enabled:
                    raise
                bounded_result = None
                bounded_reason = "sql_error"
                log_event("safe_geometry_bounded_error", profile=profile, mode=mode_value, reason=exc.__class__.__name__)

            if bounded_result is not None and not _safe_geometry_suspicious(float(bounded_result["distance_m"]), direct_meters):
                return bounded_result

            if not settings.route_safe_corridor_fallback_enabled:
                return bounded_result

            fallback_reason = bounded_reason or "suspicious_distance"
            inc("saferoute_safe_geometry_fallback_total", {"profile": profile, "mode": mode_value, "reason": fallback_reason})
            log_event("safe_geometry_fallback", profile=profile, mode=mode_value, reason=fallback_reason)
            fallback_result, _ = _fetch_safe_geometry_scope(
                conn,
                profile,
                lat1,
                lon1,
                lat2,
                lon2,
                mode=mode_value,
                scope="fallback",
                corridor_filter_sql=None,
            )
            return fallback_result

        result, _ = _fetch_safe_geometry_scope(
            conn,
            profile,
            lat1,
            lon1,
            lat2,
            lon2,
            mode=mode_value,
            scope="full",
            corridor_filter_sql=None,
        )
        return result


def trace_safe_route(profile: str, geometry: Dict[str, Any], distance_m: int) -> Optional[Dict[str, Any]]:
    """Snap a safety-first route through Valhalla trace_route for real maneuvers."""

    coordinates = flatten_geometry_coordinates(geometry)
    if len(coordinates) < 2:
        return None
    shape = simplify_coordinates(coordinates)
    payload = {
        "shape": [{"lat": point["lat"], "lon": point["lon"]} for point in shape],
        "costing": VALHALLA_COSTING[profile],
        "shape_match": "map_snap",
        "directions_options": {"language": "ru-RU", "units": "kilometers"},
    }
    try:
        traced, _, source_url = fetch_dependency_json("valhalla", "POST", "/trace_route", json_body=payload)
    except DependencyCallError:
        return None

    source = "postgis+valhalla-public-trace" if "openstreetmap.de" in source_url else "postgis+valhalla-trace"
    route = normalize_trip_route(traced.get("trip") or {}, source=source, profile=profile)
    if route is None:
        return None
    route["geometry"] = geometry
    route["distance_m"] = distance_m
    route["estimated_mins"] = estimate_minutes(distance_m, profile)
    route["bbox"] = geometry_bounds(geometry)
    return route


def _optional_float(value: object) -> float | None:
    """Convert nullable DB aggregate values to optional floats."""

    if value is None:
        return None
    return float(str(value))


def score_route_geometry(geometry: Dict[str, Any], profile: str, mode: str | RoutingMode) -> RouteScoreResult:
    """Compute route score by sampling nearest real safety graph edges."""

    graph_columns = get_network_columns()
    enrichment_columns = get_enrichment_columns()
    nearest_edges_cte, scoring_columns = scoring_edges_cte_sql(graph_columns, enrichment_columns)
    geometry_json = json.dumps(sampling_line_geometry(geometry), separators=(",", ":"))
    query = text(
        f"""
        WITH route AS (
            SELECT ST_LineMerge(ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326)) AS geom
        ),
        sample_steps AS (
            SELECT generate_series(0.0, 1.0, 0.04) AS fraction
        ),
        sample_points AS (
            SELECT ST_LineInterpolatePoint(route.geom, sample_steps.fraction) AS point
            FROM route
            CROSS JOIN sample_steps
            WHERE route.geom IS NOT NULL
        ),
        {nearest_edges_cte}
        {route_attribute_summary_sql(scoring_columns)}
        """
    )
    with get_engine().connect() as conn:
        row = conn.execute(query, {"geometry": geometry_json}).mappings().one()
    summary = RouteAttributeSummary(
        avg_safety_weight=_optional_float(row["avg_safety_weight"]),
        min_width_m=_optional_float(row["min_width_m"]),
        max_speed_kmh=_optional_float(row["max_speed_kmh"]),
        max_lanes=_optional_float(row["max_lanes"]),
        track_fraction=float(row["track_fraction"] or 0.0),
        bike_lane_fraction=float(row["bike_lane_fraction"] or 0.0),
        walk_friendly_fraction=float(row["walk_friendly_fraction"] or 0.0),
        bad_surface_fraction=_optional_float(row["bad_surface_fraction"]),
        smooth_surface_fraction=_optional_float(row["smooth_surface_fraction"]),
        broken_surface_fraction=_optional_float(row["broken_surface_fraction"]),
        sidewalk_missing_fraction=_optional_float(row["sidewalk_missing_fraction"]),
        min_sidewalk_width_m=_optional_float(row["min_sidewalk_width_m"]),
        avg_curb_risk=_optional_float(row["avg_curb_risk"]),
        max_curb_frequency=_optional_float(row["max_curb_frequency"]),
        max_curb_density_per_km=_optional_float(row["max_curb_density_per_km"]),
        crossing_count=_optional_float(row["crossing_count"]),
        controlled_crossing_count=_optional_float(row["controlled_crossing_count"]),
        uncontrolled_crossing_count=_optional_float(row["uncontrolled_crossing_count"]),
        avg_crossing_risk=_optional_float(row["avg_crossing_risk"]),
        poor_lighting_fraction=_optional_float(row["poor_lighting_fraction"]),
        good_lighting_fraction=_optional_float(row["good_lighting_fraction"]),
        max_slope_percent=_optional_float(row["max_slope_percent"]),
        avg_traffic_intensity=_optional_float(row["avg_traffic_intensity"]),
        avg_pedestrian_density=_optional_float(row["avg_pedestrian_density"]),
        micromobility_forbidden_fraction=_optional_float(row["micromobility_forbidden_fraction"]),
        forbidden_zone_fraction=_optional_float(row["forbidden_zone_fraction"]),
        micromobility_slow_zone_fraction=_optional_float(row["micromobility_slow_zone_fraction"]),
        min_zone_speed_limit_kmh=_optional_float(row["min_zone_speed_limit_kmh"]),
        avg_road_exposure_proxy=_optional_float(row["avg_road_exposure_proxy"]),
        avg_weather_sensitive_risk=_optional_float(row["avg_weather_sensitive_risk"]),
        avg_enrichment_confidence=_optional_float(row["avg_enrichment_confidence"]),
        avg_telemetry_confidence=_optional_float(row["avg_telemetry_confidence"]),
    )
    data_sources: dict[str, object] = {}
    weather = get_route_weather_risk(geometry)
    if weather is not None:
        summary = replace(summary, avg_weather_sensitive_risk=weather.risk, weather_confidence=weather.confidence)
        data_sources["weather"] = weather.source
    telemetry = get_route_telemetry_confidence(geometry)
    if telemetry is not None:
        summary = replace(summary, avg_telemetry_confidence=telemetry.confidence)
        data_sources["telemetry"] = telemetry.source
    result = calculate_route_score(summary, mode, profile)
    if data_sources:
        return RouteScoreResult(
            mode=result.mode,
            total=result.total,
            safety_index=result.safety_index,
            reasons=result.reasons,
            factors=result.factors,
            data_sources=data_sources,
        )
    return result


def enrich_safety(geometry: Dict[str, Any]) -> int:
    """Compute legacy route safety using the default walking scoring mode."""

    return score_route_geometry(geometry, profile="walk", mode=RoutingMode.SAFEST).safety_index


def build_route_feature(profile: str, variant: str, route_data: Dict[str, Any], *, mode: str | RoutingMode = "safest") -> RouteFeature:
    """Build one public route feature."""

    mode_value = normalize_route_mode(mode).value
    bbox = route_data.get("bbox") or geometry_bounds(route_data["geometry"])
    score = route_data.get("score")
    source = str(route_data["source"])
    if isinstance(score, RouteScoreResult):
        score_payload = score.to_public_dict()
        raw_data_sources = score_payload.get("data_sources")
        data_sources: dict[str, Any] = raw_data_sources if isinstance(raw_data_sources, dict) else {}
        data_sources["enrichment"] = get_active_enrichment_public_metadata()
        score_payload["data_sources"] = data_sources
        score_details = RouteScoreDetails.model_validate(score_payload)
    else:
        score_details = None
    is_unscored_fallback = score_details is None and "unscored" in source
    label = VARIANT_LABELS[variant]
    subtitle = VARIANT_SUBTITLES[profile][variant]
    if is_unscored_fallback:
        label = "Маршрут Valhalla" if variant == "safe" else "Альтернатива Valhalla"
        subtitle = "Навигация доступна, но PostGIS-оценка безопасности сейчас недоступна"

    return RouteFeature(
        id=f"{profile}-{variant}",
        label=label,
        subtitle=subtitle,
        properties=RouteProperties(
            distance_m=int(route_data["distance_m"]),
            estimated_mins=int(route_data["estimated_mins"]),
            safety_index=int(route_data["safety_index"]),
            profile=profile,
            variant=variant,
            mode=mode_value,
            instructions=route_data["instructions"],
            bbox=bbox,
            source=source,
            navigable=True,
            score=score_details,
        ),
        geometry=route_data["geometry"],
    )


def route_tradeoff_key(route_data: Dict[str, Any], mode: str | RoutingMode = "balanced") -> Tuple[float, float]:
    """Rank balanced routes by safety first, ETA second."""

    safety = float(route_data["safety_index"]) / 100.0
    minutes = float(route_data["estimated_mins"])
    distance = float(route_data["distance_m"])
    if normalize_route_mode(mode) == RoutingMode.FASTEST:
        return (minutes, -safety)
    if normalize_route_mode(mode) == RoutingMode.ACCESSIBLE:
        return (-safety, distance)
    return (-safety, minutes)


def route_geometry_key(route_data: Dict[str, Any]) -> str:
    """Return a stable geometry key for exact duplicate route removal."""

    return json.dumps(route_data["geometry"], separators=(",", ":"))


def assign_route_variants(
    profile: str,
    *,
    safe_route: Optional[Dict[str, Any]],
    candidates: List[Dict[str, Any]],
    alternatives: int,
    mode: str | RoutingMode = "safest",
) -> List[RouteFeature]:
    """Assign truthful safe/balanced/fast roles to distinct real route candidates."""

    mode_value = normalize_route_mode(mode).value
    distinct: List[Dict[str, Any]] = []
    seen_shapes: set[str] = set()
    for route in ([safe_route] if safe_route is not None else []) + candidates:
        if route is None:
            continue
        shape_key = route_geometry_key(route)
        if shape_key in seen_shapes:
            continue
        seen_shapes.add(shape_key)
        distinct.append(route)

    if not distinct:
        return []

    labeled_routes: List[RouteFeature] = []
    used_ids: set[int] = set()

    safety_route = max(
        distinct,
        key=lambda item: (float(item["safety_index"]), -float(item["estimated_mins"])),
    )
    used_ids.add(id(safety_route))
    labeled_routes.append(build_route_feature(profile, "safe", safety_route, mode=mode_value))

    remaining = [route for route in distinct if id(route) not in used_ids]
    if remaining:
        fastest_route = min(remaining, key=lambda item: float(item["estimated_mins"]))
        if float(fastest_route["estimated_mins"]) <= float(safety_route["estimated_mins"]):
            used_ids.add(id(fastest_route))
            labeled_routes.append(build_route_feature(profile, "fast", fastest_route, mode=mode_value))

    remaining = [route for route in distinct if id(route) not in used_ids]
    if remaining:
        balanced_route = min(remaining, key=lambda route: route_tradeoff_key(route, mode_value))
        labeled_routes.append(build_route_feature(profile, "balanced", balanced_route, mode=mode_value))

    ordered = sorted(labeled_routes, key=lambda route: VARIANT_ORDER.index(route.properties.variant))
    return ordered[:alternatives]


def build_route_set(
    profile: str,
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    alternatives: int,
    *,
    mode: str | RoutingMode = "safest",
) -> List[RouteFeature]:
    """Assemble stable safe/balanced/fast routes for the UI."""

    mode_value = normalize_route_mode(mode).value
    key = route_cache_key(profile, lat1, lon1, lat2, lon2, alternatives, mode_value)
    cached = cache_get(key)
    if cached is not None:
        log_event("route_cache_hit", profile=profile, mode=mode_value, routes=len(cached))
        return cached

    try:
        candidates = fetch_valhalla_routes(profile, lat1, lon1, lat2, lon2, alternatives=max(2, alternatives))
        safe_route = None
        try:
            for candidate in candidates:
                score = score_route_geometry(candidate["geometry"], profile=profile, mode=mode_value)
                candidate["safety_index"] = score.safety_index
                candidate["score"] = score

            safe_geometry = fetch_safe_geometry(profile, lat1, lon1, lat2, lon2, mode=mode_value)
            if safe_geometry is not None:
                safe_route = trace_safe_route(profile, safe_geometry["geometry"], safe_geometry["distance_m"])
                if safe_route is not None:
                    score = score_route_geometry(safe_route["geometry"], profile=profile, mode=mode_value)
                    safe_route["safety_index"] = score.safety_index
                    safe_route["score"] = score
        except SQLAlchemyError as exc:
            apply_unscored_safety_fallback(candidates, profile, mode_value, exc.__class__.__name__)

        ordered = assign_route_variants(profile, safe_route=safe_route, candidates=candidates, alternatives=alternatives, mode=mode_value)
        cache_set(key, ordered)
        for route in ordered:
            inc("saferoute_route_variants_total", {"profile": profile, "mode": mode_value, "variant": route.properties.variant})
        log_event("route_response", profile=profile, mode=mode_value, variants=[route.properties.variant for route in ordered], count=len(ordered))
        return ordered
    except Exception as exc:
        inc("saferoute_route_failures_total", {"profile": profile, "reason": exc.__class__.__name__})
        raise


def explain_safe_route(profile: str, lat1: float, lon1: float, lat2: float, lon2: float) -> List[str]:
    """Return an EXPLAIN plan for profiling the safety route query."""

    algorithm = "astar" if should_use_astar() else "dijkstra"
    query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {build_safe_route_query(profile, PROFILE_FILTERS[profile], mode='safest', algorithm=algorithm)}"
    with get_engine().connect() as conn:
        rows = conn.execute(text(query), {"lat1": lat1, "lon1": lon1, "lat2": lat2, "lon2": lon2})
        return [str(row[0]) for row in rows]
