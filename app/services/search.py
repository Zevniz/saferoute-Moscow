"""Photon search and reverse geocoding service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.core.config import get_settings
from app.schemas.routing import ReverseResult, SearchResult
from app.services.http import DependencyCallError, fetch_dependency_json

MOSCOW_CENTER = {"lat": 55.7558, "lon": 37.6173}
MOSCOW_LANDMARKS = [
    {
        "id": "landmark:moscow-kremlin",
        "label": "Московский Кремль, Москва",
        "lat": 55.7520233,
        "lon": 37.6174994,
        "bbox": [37.6130, 55.7470, 37.6230, 55.7565],
        "kind": "landmark",
        "aliases": ("кремль", "московский кремль", "kremlin", "moscow kremlin"),
    },
    {
        "id": "landmark:red-square",
        "label": "Красная площадь, Москва",
        "lat": 55.7539303,
        "lon": 37.620795,
        "bbox": [37.6184, 55.7522, 37.6231, 55.7552],
        "kind": "landmark",
        "aliases": ("красная площадь", "red square"),
    },
    {
        "id": "landmark:gorky-park",
        "label": "Парк Горького, Москва",
        "lat": 55.729804,
        "lon": 37.603033,
        "bbox": [37.5860, 55.7150, 37.6250, 55.7400],
        "kind": "park",
        "aliases": ("парк горького", "gorky park", "горького"),
    },
]


def normalize_query(value: str) -> str:
    """Normalize a user search query for lightweight local landmark ranking."""

    return " ".join(value.casefold().replace("ё", "е").split())


def within_moscow(lat: float, lon: float) -> bool:
    """Return whether coordinates are inside the configured Moscow bbox."""

    settings = get_settings()
    return (
        settings.moscow_min_lat <= lat <= settings.moscow_max_lat
        and settings.moscow_min_lon <= lon <= settings.moscow_max_lon
    )


def bbox_from_extent(extent: Any) -> Optional[List[float]]:
    """Normalize Photon extent into a GeoJSON bbox."""

    if not isinstance(extent, list) or len(extent) != 4:
        return None
    return [float(value) for value in extent]


def photon_feature_to_result(feature: Dict[str, Any]) -> Optional[SearchResult]:
    """Convert a Photon feature into the SafeRoute search contract."""

    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") or []
    if len(coordinates) < 2:
        return None

    lon, lat = float(coordinates[0]), float(coordinates[1])
    properties = feature.get("properties") or {}
    parts = [
        properties.get("name"),
        properties.get("street"),
        properties.get("district"),
        properties.get("city"),
        properties.get("state"),
    ]
    label = ", ".join(str(value) for value in parts if value) or properties.get("country") or "Точка на карте"
    kind = properties.get("osm_value") or properties.get("type") or properties.get("osm_key") or "place"

    return SearchResult(
        id=str(properties.get("osm_id") or feature.get("id") or label),
        label=label,
        lat=lat,
        lon=lon,
        bbox=bbox_from_extent(properties.get("extent")),
        kind=str(kind),
    )


def local_landmark_matches(query: str, limit: int) -> List[SearchResult]:
    """Return high-confidence Moscow landmarks that Photon often under-ranks."""

    normalized = normalize_query(query)
    matches: List[SearchResult] = []
    for landmark in MOSCOW_LANDMARKS:
        aliases = [normalize_query(alias) for alias in landmark["aliases"]]
        if normalized in aliases or any(alias in normalized for alias in aliases if len(alias) >= 5):
            matches.append(
                SearchResult(
                    id=str(landmark["id"]),
                    label=str(landmark["label"]),
                    lat=float(landmark["lat"]),
                    lon=float(landmark["lon"]),
                    bbox=list(landmark["bbox"]),
                    kind=str(landmark["kind"]),
                )
            )
    return matches[:limit]


def merge_ranked_results(primary: List[SearchResult], secondary: List[SearchResult], limit: int) -> List[SearchResult]:
    """Merge result lists while preserving order and removing duplicate IDs."""

    seen: set[str] = set()
    merged: List[SearchResult] = []
    for item in [*primary, *secondary]:
        if item.id in seen:
            continue
        seen.add(item.id)
        merged.append(item)
        if len(merged) >= limit:
            break
    return merged


def search_places(query: str, limit: int) -> List[SearchResult]:
    """Search Moscow-biased places through Photon."""

    landmark_results = local_landmark_matches(query, limit)
    params = {
        "q": query,
        "limit": max(1, min(limit, 8)),
        "lat": MOSCOW_CENTER["lat"],
        "lon": MOSCOW_CENTER["lon"],
    }
    try:
        payload, _, _ = fetch_dependency_json("photon", "GET", "/api", params=params)
    except DependencyCallError as exc:
        raise HTTPException(status_code=503, detail="Поиск мест временно недоступен") from exc

    results = [
        item
        for feature in payload.get("features", [])
        if (item := photon_feature_to_result(feature)) is not None
    ]

    preferred = [item for item in results if within_moscow(item.lat, item.lon)]
    ranked = preferred if preferred else results
    return merge_ranked_results(landmark_results, ranked, limit)


def reverse_place(lat: float, lon: float) -> ReverseResult:
    """Reverse geocode a point through Photon."""

    try:
        payload, _, source_url = fetch_dependency_json("photon", "GET", "/reverse", params={"lat": lat, "lon": lon})
    except DependencyCallError as exc:
        raise HTTPException(status_code=503, detail="Обратное геокодирование временно недоступно") from exc

    feature = next(iter(payload.get("features", [])), None)
    if not feature:
        raise HTTPException(status_code=404, detail="Адрес рядом с точкой не найден")

    result = photon_feature_to_result(feature)
    if result is None:
        raise HTTPException(status_code=404, detail="Адрес рядом с точкой не найден")

    source = "photon-public-fallback" if "komoot.io" in source_url else "photon"
    return ReverseResult(**result.model_dump(), source=source)
