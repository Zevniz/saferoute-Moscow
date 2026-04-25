"""Geometry utilities shared by routing and telemetry services."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


def decode_polyline(encoded: str, precision: int = 6) -> List[List[float]]:
    """Decode a Valhalla polyline into GeoJSON `[lon, lat]` coordinates."""

    coordinates: List[List[float]] = []
    index = 0
    lat = 0
    lon = 0
    factor = 10**precision

    while index < len(encoded):
        shift = 0
        result = 0
        while True:
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lat = ~(result >> 1) if result & 1 else result >> 1
        lat += delta_lat

        shift = 0
        result = 0
        while True:
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lon = ~(result >> 1) if result & 1 else result >> 1
        lon += delta_lon
        coordinates.append([lon / factor, lat / factor])

    return coordinates


def flatten_geometry_coordinates(geometry: Dict[str, Any]) -> List[List[float]]:
    """Return a flat coordinate list for LineString and MultiLineString."""

    coordinates = geometry.get("coordinates") or []
    if geometry.get("type") == "LineString":
        return coordinates
    if geometry.get("type") == "MultiLineString":
        return [point for line in coordinates for point in line]
    return []


def geometry_bounds(geometry: Dict[str, Any]) -> Optional[List[float]]:
    """Return GeoJSON bbox `[minLon, minLat, maxLon, maxLat]`."""

    points = flatten_geometry_coordinates(geometry)
    if not points:
        return None
    min_lon = min(point[0] for point in points)
    min_lat = min(point[1] for point in points)
    max_lon = max(point[0] for point in points)
    max_lat = max(point[1] for point in points)
    return [min_lon, min_lat, max_lon, max_lat]


def point_distance(point: List[float], lon: float, lat: float) -> float:
    """Return a lightweight planar distance in degrees for orientation checks."""

    return math.hypot(float(point[0]) - lon, float(point[1]) - lat)


def orient_geometry(geometry: Dict[str, Any], lat1: float, lon1: float, lat2: float, lon2: float) -> Dict[str, Any]:
    """Orient route geometry from origin to destination."""

    coordinates = geometry.get("coordinates") or []
    if not coordinates:
        return geometry

    if geometry.get("type") == "LineString":
        lines = [coordinates]
    elif geometry.get("type") == "MultiLineString":
        lines = coordinates
    else:
        return geometry

    if not lines or not lines[0]:
        return geometry

    first = lines[0][0]
    last = lines[-1][-1]
    start_alignment = point_distance(first, lon1, lat1) + point_distance(last, lon2, lat2)
    reverse_alignment = point_distance(first, lon2, lat2) + point_distance(last, lon1, lat1)
    if start_alignment <= reverse_alignment:
        return geometry

    reversed_lines = [list(reversed(line)) for line in reversed(lines)]
    if geometry.get("type") == "LineString":
        return {"type": "LineString", "coordinates": reversed_lines[0]}
    return {"type": "MultiLineString", "coordinates": reversed_lines}


def sampling_line_geometry(geometry: Dict[str, Any]) -> Dict[str, Any]:
    """Convert MultiLineString to LineString for PostGIS line interpolation."""

    if geometry.get("type") == "LineString":
        return geometry
    if geometry.get("type") == "MultiLineString":
        return {"type": "LineString", "coordinates": flatten_geometry_coordinates(geometry)}
    return geometry


def simplify_coordinates(coordinates: List[List[float]], max_points: int = 96) -> List[Dict[str, float]]:
    """Downsample route coordinates before Valhalla trace_route calls."""

    if len(coordinates) <= max_points:
        return [{"lon": lon, "lat": lat} for lon, lat in coordinates]

    stride = max(1, math.ceil(len(coordinates) / max_points))
    reduced = coordinates[::stride]
    if reduced[-1] != coordinates[-1]:
        reduced.append(coordinates[-1])
    return [{"lon": lon, "lat": lat} for lon, lat in reduced]


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a numeric value."""

    return min(maximum, max(minimum, value))

