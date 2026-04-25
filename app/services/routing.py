"""Route assembly service combining Valhalla and PostGIS safety data."""

from __future__ import annotations

import json
import time
from collections import OrderedDict
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


def route_cache_key(profile: str, lat1: float, lon1: float, lat2: float, lon2: float, alternatives: int, mode: str | RoutingMode) -> Tuple[Any, ...]:
    """Build a normalized in-memory route cache key."""

    precision = get_settings().route_bucket_precision
    return (
        get_settings().route_data_version,
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
    return bool(exists)


def node_cte_sql(filter_sql: str) -> str:
    """Build nearest-node CTE source using materialized nodes when available."""

    if use_materialized_nodes():
        return """
            SELECT node_id, geometry AS node_geometry
            FROM moscow_network_nodes
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


def build_safe_route_query(profile: str, filter_sql: str, mode: str | RoutingMode = "safest", algorithm: str = "astar") -> str:
    """Build pgRouting SQL for the safety-first route."""

    filter_sql = " ".join(combined_filter_sql(profile, filter_sql, mode, get_network_columns()).split())
    route_sql = build_edge_sql(profile, filter_sql, mode).replace("'", "''")
    node_source_sql = node_cte_sql(filter_sql)
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


def fetch_safe_geometry(profile: str, lat1: float, lon1: float, lat2: float, lon2: float, *, mode: str | RoutingMode) -> Optional[Dict[str, Any]]:
    """Fetch a safety-first geometry from PostGIS/pgRouting."""

    mode_value = normalize_route_mode(mode).value
    started = time.perf_counter()
    with get_engine().connect() as conn:
        for filter_sql in PROFILE_FILTER_CANDIDATES[profile]:
            algorithms = ["astar", "dijkstra"] if should_use_astar() else ["dijkstra"]
            row = None
            used_algorithm = algorithms[0]
            for algorithm in algorithms:
                try:
                    row = conn.execute(
                        text(build_safe_route_query(profile, filter_sql, mode=mode_value, algorithm=algorithm)),
                        {"lat1": lat1, "lon1": lon1, "lat2": lat2, "lon2": lon2},
                    ).mappings().one()
                    used_algorithm = algorithm
                    break
                except SQLAlchemyError as exc:
                    if algorithm == algorithms[-1]:
                        raise
                    log_event("safe_geometry_algorithm_fallback", profile=profile, from_algorithm=algorithm, reason=exc.__class__.__name__)
                    inc("saferoute_route_failures_total", {"profile": profile, "reason": f"{algorithm}_failed"})
            if row is None:
                continue
            geometry_json = row.get("geometry")
            if not geometry_json or not row.get("distance_meters"):
                continue
            geometry = json.loads(geometry_json) if isinstance(geometry_json, str) else geometry_json
            geometry = orient_geometry(geometry, lat1, lon1, lat2, lon2)
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            observe("saferoute_safe_geometry_duration_ms", duration_ms, {"profile": profile, "mode": mode_value, "algorithm": used_algorithm})
            log_event("safe_geometry", profile=profile, mode=mode_value, algorithm=used_algorithm, duration_ms=duration_ms)
            return {"geometry": geometry, "distance_m": round(float(row["distance_meters"]))}
    return None


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

    columns = get_network_columns()
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
        nearest_edges AS (
            SELECT edge.*
            FROM sample_points
            CROSS JOIN LATERAL (
                SELECT *
                FROM moscow_network
                ORDER BY geometry <-> sample_points.point
                LIMIT 1
            ) AS edge
        )
        {route_attribute_summary_sql(columns)}
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
    )
    return calculate_route_score(summary, mode, profile)


def enrich_safety(geometry: Dict[str, Any]) -> int:
    """Compute legacy route safety using the default walking scoring mode."""

    return score_route_geometry(geometry, profile="walk", mode=RoutingMode.SAFEST).safety_index


def build_route_feature(profile: str, variant: str, route_data: Dict[str, Any], *, mode: str | RoutingMode = "safest") -> RouteFeature:
    """Build one public route feature."""

    mode_value = normalize_route_mode(mode).value
    bbox = route_data.get("bbox") or geometry_bounds(route_data["geometry"])
    score = route_data.get("score")
    score_details = RouteScoreDetails.model_validate(score.to_public_dict()) if isinstance(score, RouteScoreResult) else None
    return RouteFeature(
        id=f"{profile}-{variant}",
        label=VARIANT_LABELS[variant],
        subtitle=VARIANT_SUBTITLES[profile][variant],
        properties=RouteProperties(
            distance_m=int(route_data["distance_m"]),
            estimated_mins=int(route_data["estimated_mins"]),
            safety_index=int(route_data["safety_index"]),
            profile=profile,
            variant=variant,
            mode=mode_value,
            instructions=route_data["instructions"],
            bbox=bbox,
            source=str(route_data["source"]),
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
        for candidate in candidates:
            score = score_route_geometry(candidate["geometry"], profile=profile, mode=mode_value)
            candidate["safety_index"] = score.safety_index
            candidate["score"] = score

        safe_route = None
        safe_geometry = fetch_safe_geometry(profile, lat1, lon1, lat2, lon2, mode=mode_value)
        if safe_geometry is not None:
            safe_route = trace_safe_route(profile, safe_geometry["geometry"], safe_geometry["distance_m"])
            if safe_route is not None:
                score = score_route_geometry(safe_route["geometry"], profile=profile, mode=mode_value)
                safe_route["safety_index"] = score.safety_index
                safe_route["score"] = score

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
