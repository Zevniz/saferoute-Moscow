#!/usr/bin/env python3
"""Validate official micromobility zone GeoJSON before PostGIS import."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

ZONE_TYPES = {"forbidden", "slow", "preferred", "dedicated"}
SCORED_ZONE_TYPES = {"forbidden", "slow"}
GEOMETRY_TYPES = {"Polygon", "MultiPolygon"}


class ZoneValidationError(ValueError):
    """Raised when a zone source cannot be safely imported."""


def _fail(message: str) -> None:
    raise ZoneValidationError(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value: Any, label: str, *, required: bool, min_value: float | None = None, max_value: float | None = None) -> float | None:
    if value is None or value == "":
        if required:
            _fail(f"{label} is required")
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        _fail(f"{label} must be numeric")
    if not math.isfinite(parsed):
        _fail(f"{label} must be finite")
    if min_value is not None and parsed < min_value:
        _fail(f"{label} must be >= {min_value}")
    if max_value is not None and parsed > max_value:
        _fail(f"{label} must be <= {max_value}")
    return parsed


def _validate_crs(payload: dict[str, Any]) -> str:
    crs = payload.get("crs")
    if crs is None:
        return "EPSG:4326"
    if not isinstance(crs, dict):
        _fail("GeoJSON crs must be an object when present")
    properties = crs.get("properties")
    name = properties.get("name") if isinstance(properties, dict) else None
    normalized = str(name or "").lower()
    if "epsg:4326" in normalized or "ogc:crs84" in normalized or normalized.endswith("crs84"):
        return "EPSG:4326"
    _fail("GeoJSON source CRS must be EPSG:4326/CRS84 or omitted per RFC 7946")


def _position(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) < 2:
        _fail(f"{label} must be a coordinate position")
    lon = _number(value[0], f"{label}.lon", required=True, min_value=-180, max_value=180)
    lat = _number(value[1], f"{label}.lat", required=True, min_value=-90, max_value=90)
    assert lon is not None and lat is not None
    return lon, lat


def _validate_ring(ring: Any, label: str) -> list[tuple[float, float]]:
    if not isinstance(ring, list) or len(ring) < 4:
        _fail(f"{label} must have at least four positions")
    positions = [_position(position, f"{label}[{index}]") for index, position in enumerate(ring)]
    if positions[0] != positions[-1]:
        _fail(f"{label} must be closed")
    return positions


def _validate_polygon(coordinates: Any, label: str) -> list[tuple[float, float]]:
    if not isinstance(coordinates, list) or not coordinates:
        _fail(f"{label} must contain at least one ring")
    positions: list[tuple[float, float]] = []
    for index, ring in enumerate(coordinates):
        positions.extend(_validate_ring(ring, f"{label}.ring[{index}]"))
    return positions


def _validate_geometry(geometry: Any, feature_number: int) -> tuple[str, list[tuple[float, float]]]:
    if not isinstance(geometry, dict):
        _fail(f"feature {feature_number}: geometry must be an object")
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type not in GEOMETRY_TYPES:
        _fail(f"feature {feature_number}: geometry type must be Polygon or MultiPolygon")
    positions: list[tuple[float, float]] = []
    if geometry_type == "Polygon":
        positions.extend(_validate_polygon(coordinates, f"feature {feature_number}.polygon"))
    else:
        if not isinstance(coordinates, list) or not coordinates:
            _fail(f"feature {feature_number}: MultiPolygon must contain polygons")
        for index, polygon in enumerate(coordinates):
            positions.extend(_validate_polygon(polygon, f"feature {feature_number}.multipolygon[{index}]"))
    return str(geometry_type), positions


def _feature_id(feature: dict[str, Any], feature_number: int, seen: set[str]) -> str:
    properties = feature.get("properties")
    props = properties if isinstance(properties, dict) else {}
    raw_id = props.get("source_id") or feature.get("id") or f"feature-{feature_number:06d}"
    feature_id = str(raw_id).strip()
    if not feature_id:
        feature_id = f"feature-{feature_number:06d}"
    if feature_id in seen:
        _fail(f"feature {feature_number}: duplicate source_id/id '{feature_id}'")
    seen.add(feature_id)
    return feature_id


def _normalized_feature(feature: dict[str, Any], feature_number: int, seen_ids: set[str]) -> dict[str, str]:
    properties = feature.get("properties")
    if not isinstance(properties, dict):
        _fail(f"feature {feature_number}: properties must be an object")
    zone_type = str(properties.get("zone_type", "")).strip().lower()
    if zone_type not in ZONE_TYPES:
        _fail(f"feature {feature_number}: zone_type must be one of {', '.join(sorted(ZONE_TYPES))}")
    confidence = _number(properties.get("confidence"), f"feature {feature_number}: confidence", required=True, min_value=0, max_value=1)
    speed_limit = _number(
        properties.get("zone_speed_limit_kmh", properties.get("speed_limit_kmh")),
        f"feature {feature_number}: zone_speed_limit_kmh",
        required=zone_type == "slow",
        min_value=0,
    )
    if zone_type != "slow" and speed_limit is not None:
        _fail(f"feature {feature_number}: zone_speed_limit_kmh is only accepted for slow zones")
    geometry = feature.get("geometry")
    geometry_type, _ = _validate_geometry(geometry, feature_number)
    assert confidence is not None
    return {
        "feature_id": _feature_id(feature, feature_number, seen_ids),
        "zone_type": zone_type,
        "zone_speed_limit_kmh": "" if speed_limit is None else str(speed_limit),
        "confidence": str(confidence),
        "geometry_type": geometry_type,
        "geometry_json": json.dumps(geometry, ensure_ascii=False, separators=(",", ":")),
    }


def normalize_geojson(source_path: Path, target_csv_path: Path, report_path: Path) -> dict[str, Any]:
    with source_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        _fail("micromobility zone source must be a GeoJSON FeatureCollection")
    crs = _validate_crs(payload)
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        _fail("micromobility zone source has no features")

    normalized_rows: list[dict[str, str]] = []
    zone_type_counts = {zone_type: 0 for zone_type in sorted(ZONE_TYPES)}
    scored_feature_count = 0
    confidence_total = 0.0
    bbox = [180.0, 90.0, -180.0, -90.0]
    seen_ids: set[str] = set()
    for index, feature in enumerate(features, start=1):
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            _fail(f"feature {index}: expected GeoJSON Feature")
        row = _normalized_feature(feature, index, seen_ids)
        geometry_type, positions = _validate_geometry(feature.get("geometry"), index)
        row["geometry_type"] = geometry_type
        for lon, lat in positions:
            bbox[0] = min(bbox[0], lon)
            bbox[1] = min(bbox[1], lat)
            bbox[2] = max(bbox[2], lon)
            bbox[3] = max(bbox[3], lat)
        zone_type_counts[row["zone_type"]] += 1
        if row["zone_type"] in SCORED_ZONE_TYPES:
            scored_feature_count += 1
        confidence_total += float(row["confidence"])
        normalized_rows.append(row)

    target_csv_path.parent.mkdir(parents=True, exist_ok=True)
    with target_csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["feature_id", "zone_type", "zone_speed_limit_kmh", "confidence", "geometry_type", "geometry_json"],
        )
        writer.writeheader()
        writer.writerows(normalized_rows)

    report = {
        "source_file": str(source_path),
        "source_sha256": _sha256(source_path),
        "crs": crs,
        "feature_count": len(normalized_rows),
        "scored_feature_count": scored_feature_count,
        "zone_type_counts": zone_type_counts,
        "avg_confidence": round(confidence_total / len(normalized_rows), 6),
        "bbox": bbox,
        "production_activation_note": "Only forbidden and slow zones currently map to SafeRoute scoring fields.",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("Usage: validate-micromobility-zones.py source.geojson normalized.csv report.json", file=sys.stderr)
        return 2
    try:
        report = normalize_geojson(Path(argv[1]), Path(argv[2]), Path(argv[3]))
    except (OSError, json.JSONDecodeError, ZoneValidationError) as exc:
        print(f"fail: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
