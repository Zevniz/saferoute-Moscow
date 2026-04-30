#!/usr/bin/env python3
"""Build real OSM-derived curb or crossing enrichment from a local PBF.

The importer uses only OpenStreetMap features present in the configured
Geofabrik extract. Edge mapping is an audited spatial join to
public.moscow_network with distance and ambiguity thresholds.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median
from pathlib import Path
from typing import Any, Iterable

import psycopg2
from psycopg2.extensions import connection as PgConnection

DEFAULT_SOURCE_URL = "https://download.geofabrik.de/russia/central-fed-district.html"
OSM_COPYRIGHT_URL = "https://www.openstreetmap.org/copyright"
OSM_KERB_DOCS = "https://wiki.openstreetmap.org/wiki/Key:kerb"
OSM_CROSSING_DOCS = "https://wiki.openstreetmap.org/wiki/Crossings"
OSM_FOOTWAY_CROSSING_DOCS = "https://wiki.openstreetmap.org/wiki/Tag:footway%3Dcrossing"
OSM_TRAFFIC_SIGNALS_DOCS = "https://wiki.openstreetmap.org/wiki/Tag:highway%3Dtraffic_signals"

CSV_COLUMNS = [
    "edge_id",
    "confidence",
    "observed_at",
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
    "telemetry_confidence",
]

FILTERS = {
    "curb": (
        "n/kerb",
        "n/kerb:left",
        "n/kerb:right",
        "n/barrier=kerb",
        "n/highway=kerb",
        "n/kerb:height",
        "n/crossing:kerb",
        "n/sloped_curb",
        "n/ramp:kerb",
        "n/kerb:ramp",
        "n/tactile_paving",
        "n/wheelchair",
        "n/ramp",
        "w/kerb",
        "w/kerb:left",
        "w/kerb:right",
        "w/barrier=kerb",
        "w/highway=kerb",
        "w/kerb:height",
        "w/crossing:kerb",
        "w/sidewalk:left:kerb",
        "w/sidewalk:right:kerb",
        "w/sloped_curb",
        "w/ramp:kerb",
        "w/kerb:ramp",
        "w/tactile_paving",
        "w/wheelchair",
        "w/ramp",
    ),
    "crossings": (
        "n/highway=crossing",
        "n/crossing",
        "n/highway=traffic_signals",
        "w/highway=crossing",
        "w/crossing",
        "w/footway=crossing",
        "w/path=crossing",
        "w/cycleway=crossing",
    ),
}


@dataclass(frozen=True)
class OsmFeature:
    feature_id: str
    geometry_type: str
    geometry_json: str
    observed_at: str
    source_tags: dict[str, Any]
    curb_risk: float | None = None
    crossing_risk: float | None = None
    controlled_crossing_count: int | None = None
    uncontrolled_crossing_count: int | None = None


@dataclass(frozen=True)
class EdgeMapping:
    edge_id: int
    edge_length_m: float
    confidence: float
    highway: str
    access: str


@dataclass(frozen=True)
class CurbMatch:
    feature_id: str
    edge_id: int
    edge_length_m: float
    confidence: float
    distance_m: float | None
    strategy: str
    curb_risk: float
    observed_at: str
    highway: str
    access: str
    source_tags: dict[str, Any]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iso_from_osmium_timestamp(value: object) -> str:
    if value is None or value == "":
        return ""
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return str(value)


def run_osmium_geojsonseq(osm_path: Path, osmium_bin: str, factor: str) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="saferoute-osm-advanced-") as tmp_dir:
        filtered_path = Path(tmp_dir) / f"{factor}.osm.pbf"
        geojsonseq_path = Path(tmp_dir) / f"{factor}.geojsonseq"
        subprocess.run(
            [osmium_bin, "tags-filter", str(osm_path), *FILTERS[factor], "-o", str(filtered_path), "-O"],
            check=True,
        )
        subprocess.run(
            [
                osmium_bin,
                "export",
                "-f",
                "geojsonseq",
                "-u",
                "type_id",
                "-a",
                "timestamp",
                "--geometry-types",
                "point,linestring",
                str(filtered_path),
                "-o",
                str(geojsonseq_path),
                "-O",
            ],
            check=True,
        )
        features: list[dict[str, Any]] = []
        with geojsonseq_path.open(encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip().lstrip("\x1e")
                if not raw:
                    continue
                try:
                    feature = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(feature, dict):
                    features.append(feature)
        return features


def curb_risk_from_tags(tags: dict[str, Any]) -> float | None:
    kerb = first_tag_value(
        tags,
        "kerb",
        "kerb:left",
        "kerb:right",
        "crossing:kerb",
        "sidewalk:left:kerb",
        "sidewalk:right:kerb",
    )
    barrier = str(tags.get("barrier", "")).strip().lower()
    highway = str(tags.get("highway", "")).strip().lower()
    sloped_curb = str(tags.get("sloped_curb", "")).strip().lower()
    ramp_kerb = first_tag_value(tags, "ramp:kerb", "kerb:ramp")
    height = str(tags.get("kerb:height", "")).replace(" ", "").strip().lower()

    if kerb in {"lowered", "flush", "no", "none"}:
        return 0.1
    if kerb in {"raised", "rolled", "yes"}:
        return 0.8
    if kerb in {"regular", "unknown"}:
        return 0.6
    if barrier == "kerb" or highway == "kerb":
        return 0.65
    if sloped_curb in {"yes", "lowered"} or ramp_kerb in {"yes", "lowered", "flush"}:
        return 0.15
    if height:
        unit = "cm" if "cm" in height else "m" if "m" in height else ""
        normalized_height = height.replace("cm", "").replace("m", "")
        try:
            parsed = float(normalized_height)
        except ValueError:
            return None
        # OSM uses both metres and centimetres in the wild; keep this conservative.
        height_cm = parsed * 100 if unit == "m" or (not unit and parsed <= 1.0) else parsed
        if height_cm >= 6:
            return 0.75
        if height_cm >= 3:
            return 0.45
        return 0.15
    return None


def first_tag_value(tags: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(tags.get(key, "")).strip().lower()
        if value:
            return value
    return ""


def compact_source_tags(tags: dict[str, Any], factor: str) -> dict[str, str]:
    prefixes = (
        ("kerb", "curb", "barrier", "highway", "crossing", "sidewalk", "tactile_paving", "wheelchair", "ramp", "sloped_curb")
        if factor == "curb"
        else ("highway", "crossing", "footway", "path", "cycleway")
    )
    return {
        str(key): str(value)
        for key, value in tags.items()
        if any(str(key).startswith(prefix) for prefix in prefixes)
    }


def crossing_values_from_tags(tags: dict[str, Any]) -> tuple[float | None, int, int]:
    highway = str(tags.get("highway", "")).strip().lower()
    crossing = str(tags.get("crossing", "")).strip().lower()
    footway = str(tags.get("footway", "")).strip().lower()
    path = str(tags.get("path", "")).strip().lower()
    cycleway = str(tags.get("cycleway", "")).strip().lower()
    if not (
        highway in {"crossing", "traffic_signals"}
        or crossing
        or footway == "crossing"
        or path == "crossing"
        or cycleway == "crossing"
    ):
        return None, 0, 0

    if highway == "traffic_signals" or crossing in {"traffic_signals", "controlled"}:
        return 0.25, 1, 0
    if crossing in {"uncontrolled", "unmarked", "no"}:
        return 0.75, 0, 1
    if crossing in {"marked", "zebra", "island"}:
        return 0.4, 1, 0
    return 0.5, 0, 1


def normalized_features(raw_features: Iterable[dict[str, Any]], factor: str) -> list[OsmFeature]:
    features: list[OsmFeature] = []
    seen: set[str] = set()
    for feature in raw_features:
        feature_id = str(feature.get("id") or "")
        geometry = feature.get("geometry")
        properties = feature.get("properties")
        if not feature_id or not isinstance(geometry, dict) or not isinstance(properties, dict):
            continue
        geometry_type = str(geometry.get("type") or "")
        if geometry_type not in {"Point", "LineString", "MultiLineString"}:
            continue
        dedupe_key = f"{factor}:{feature_id}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        observed_at = iso_from_osmium_timestamp(properties.get("@timestamp"))
        if factor == "curb":
            curb_risk = curb_risk_from_tags(properties)
            if curb_risk is None:
                continue
            features.append(
                OsmFeature(
                    feature_id=feature_id,
                    geometry_type=geometry_type,
                    geometry_json=json.dumps(geometry, separators=(",", ":")),
                    observed_at=observed_at,
                    source_tags=compact_source_tags(properties, factor),
                    curb_risk=curb_risk,
                )
            )
            continue
        crossing_risk, controlled_count, uncontrolled_count = crossing_values_from_tags(properties)
        if crossing_risk is None:
            continue
        features.append(
            OsmFeature(
                feature_id=feature_id,
                geometry_type=geometry_type,
                geometry_json=json.dumps(geometry, separators=(",", ":")),
                observed_at=observed_at,
                source_tags=compact_source_tags(properties, factor),
                crossing_risk=crossing_risk,
                controlled_crossing_count=controlled_count,
                uncontrolled_crossing_count=uncontrolled_count,
            )
        )
    return features


def copy_features(conn: PgConnection, features: list[OsmFeature], factor: str) -> dict[str, int]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            CREATE TEMP TABLE osm_advanced_features_raw (
              feature_id TEXT NOT NULL,
              factor TEXT NOT NULL,
              geometry_type TEXT NOT NULL,
              geometry_json TEXT NOT NULL,
              source_tags JSONB NOT NULL,
              observed_at TIMESTAMPTZ,
              curb_risk DOUBLE PRECISION,
              crossing_risk DOUBLE PRECISION,
              controlled_crossing_count INTEGER,
              uncontrolled_crossing_count INTEGER
            ) ON COMMIT DROP
            """
        )
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        for feature in features:
            writer.writerow(
                [
                    feature.feature_id,
                    factor,
                    feature.geometry_type,
                    feature.geometry_json,
                    json.dumps(feature.source_tags, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                    feature.observed_at,
                    "" if feature.curb_risk is None else feature.curb_risk,
                    "" if feature.crossing_risk is None else feature.crossing_risk,
                    "" if feature.controlled_crossing_count is None else feature.controlled_crossing_count,
                    "" if feature.uncontrolled_crossing_count is None else feature.uncontrolled_crossing_count,
                ]
            )
        buffer.seek(0)
        cursor.copy_expert(
            """
            COPY osm_advanced_features_raw (
              feature_id, factor, geometry_type, geometry_json, source_tags, observed_at,
              curb_risk, crossing_risk, controlled_crossing_count, uncontrolled_crossing_count
            ) FROM STDIN WITH (FORMAT csv)
            """,
            buffer,
        )
        cursor.execute(
            """
            CREATE TEMP TABLE osm_advanced_features AS
            SELECT
              feature_id,
              factor,
              geometry_type,
              ST_SetSRID(ST_GeomFromGeoJSON(geometry_json), 4326) AS geom,
              source_tags,
              CASE WHEN geometry_type = 'Point' THEN 8.0 ELSE 5.0 END AS threshold_m,
              observed_at,
              curb_risk,
              crossing_risk,
              controlled_crossing_count,
              uncontrolled_crossing_count
            FROM osm_advanced_features_raw
            WHERE ST_IsValid(ST_SetSRID(ST_GeomFromGeoJSON(geometry_json), 4326))
            """
        )
        cursor.execute("CREATE INDEX osm_advanced_features_geom_idx ON osm_advanced_features USING GIST (geom)")
        cursor.execute("SELECT count(*), count(*) FILTER (WHERE geometry_type = 'Point') FROM osm_advanced_features")
        total, points = cursor.fetchone()
        return {"features": int(total or 0), "point_features": int(points or 0), "line_features": int((total or 0) - (points or 0))}


def load_way_edge_mapping(conn: PgConnection) -> dict[str, list[EdgeMapping]]:
    """Map OSM way ids to graph edge ids using public.moscow_network.osmid."""

    mapping: dict[str, list[EdgeMapping]] = {}
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
              id,
              osmid::TEXT,
              COALESCE(NULLIF(length, 0), ST_Length(geometry::geography)) AS edge_length_m,
              COALESCE(highway, '') AS highway,
              COALESCE(access, '') AS access
            FROM public.moscow_network
            WHERE osmid IS NOT NULL
            """
        )
        for edge_id, raw_osmid, edge_length_m, highway, access in cursor:
            way_ids = sorted(set(re.findall(r"\d+", str(raw_osmid))))
            if not way_ids:
                continue
            confidence = 0.95 if len(way_ids) == 1 else 0.85
            for way_id in way_ids:
                mapping.setdefault(way_id, []).append(
                    EdgeMapping(
                        edge_id=int(edge_id),
                        edge_length_m=float(edge_length_m or 0.0),
                        confidence=confidence,
                        highway=str(highway or ""),
                        access=str(access or ""),
                    )
                )
    return mapping


def direct_way_mapping_and_write_csv(conn: PgConnection, features: list[OsmFeature], output_path: Path, factor: str) -> dict[str, Any]:
    """Write enrichment rows by direct OSM way id to graph edge mapping."""

    way_mapping = load_way_edge_mapping(conn)
    rows_by_edge: dict[int, dict[str, Any]] = {}
    direct_features = 0
    matched_features: set[str] = set()
    unmatched_way_features = 0
    excluded_point_features = 0
    for feature in features:
        if not feature.feature_id.startswith("w"):
            excluded_point_features += 1
            continue
        direct_features += 1
        way_id = feature.feature_id[1:]
        mapped_edges = way_mapping.get(way_id)
        if not mapped_edges:
            unmatched_way_features += 1
            continue
        matched_features.add(feature.feature_id)
        for mapping in mapped_edges:
            state = rows_by_edge.setdefault(
                mapping.edge_id,
                {
                    "confidence_values": [],
                    "observed_at": "",
                    "edge_length_m": mapping.edge_length_m,
                    "curb_risks": [],
                    "curb_frequency": 0,
                    "crossing_count": 0,
                    "controlled_crossing_count": 0,
                    "uncontrolled_crossing_count": 0,
                    "crossing_risks": [],
                },
            )
            state["confidence_values"].append(mapping.confidence)
            if feature.observed_at and feature.observed_at > state["observed_at"]:
                state["observed_at"] = feature.observed_at
            if factor == "curb" and feature.curb_risk is not None:
                state["curb_risks"].append(feature.curb_risk)
                state["curb_frequency"] += 1
            if factor == "crossings" and feature.crossing_risk is not None:
                state["crossing_count"] += 1
                state["controlled_crossing_count"] += feature.controlled_crossing_count or 0
                state["uncontrolled_crossing_count"] += feature.uncontrolled_crossing_count or 0
                state["crossing_risks"].append(feature.crossing_risk)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for edge_id, state in sorted(rows_by_edge.items()):
        row = {column: "" for column in CSV_COLUMNS}
        confidence_values = state["confidence_values"]
        row["edge_id"] = str(edge_id)
        row["confidence"] = str(round(sum(confidence_values) / len(confidence_values), 3))
        row["observed_at"] = state["observed_at"]
        if factor == "curb":
            curb_risks = state["curb_risks"]
            if not curb_risks:
                continue
            curb_frequency = int(state["curb_frequency"])
            edge_length_km = max(float(state["edge_length_m"] or 0.0) / 1000.0, 0.001)
            row["curb_risk"] = str(round(sum(curb_risks) / len(curb_risks), 3))
            row["curb_frequency"] = str(curb_frequency)
            row["curb_density_per_km"] = str(round(curb_frequency / edge_length_km, 3))
        else:
            crossing_risks = state["crossing_risks"]
            if not crossing_risks:
                continue
            row["crossing_count"] = str(int(state["crossing_count"]))
            row["controlled_crossing_count"] = str(int(state["controlled_crossing_count"]))
            row["uncontrolled_crossing_count"] = str(int(state["uncontrolled_crossing_count"]))
            row["crossing_risk"] = str(round(sum(crossing_risks) / len(crossing_risks), 3))
        rows.append(row)

    with output_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    return {
        "features": len(features),
        "direct_way_features": direct_features,
        "excluded_point_or_node_features": excluded_point_features,
        "matched_features": len(matched_features),
        "accepted_features": len(matched_features),
        "unmatched_features": unmatched_way_features,
        "ambiguous_features": 0,
        "ambiguous_rate": 0.0,
        "import_rows": len(rows),
    }


PLAUSIBLE_CURB_HIGHWAY_RE = re.compile(
    r"(footway|path|pedestrian|cycleway|steps|service|living_street|residential|crossing|track)",
    re.IGNORECASE,
)
INCOMPATIBLE_CURB_HIGHWAY_RE = re.compile(r"(motorway|trunk|primary|secondary|tertiary)", re.IGNORECASE)


def is_plausible_curb_edge(highway: str, access: str) -> bool:
    access_normalized = access.strip().lower()
    if access_normalized in {"no", "private"}:
        return False
    return bool(PLAUSIBLE_CURB_HIGHWAY_RE.search(highway or ""))


def is_incompatible_curb_edge(highway: str) -> bool:
    return bool(INCOMPATIBLE_CURB_HIGHWAY_RE.search(highway or "")) and not PLAUSIBLE_CURB_HIGHWAY_RE.search(highway or "")


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def direct_curb_matches(features: list[OsmFeature], way_mapping: dict[str, list[EdgeMapping]]) -> tuple[list[CurbMatch], dict[str, Any]]:
    matches: list[CurbMatch] = []
    direct_features = 0
    matched_features: set[str] = set()
    unmatched_way_features = 0
    excluded_point_features = 0
    for feature in features:
        if feature.curb_risk is None:
            continue
        if not feature.feature_id.startswith("w"):
            excluded_point_features += 1
            continue
        direct_features += 1
        mapped_edges = way_mapping.get(feature.feature_id[1:])
        if not mapped_edges:
            unmatched_way_features += 1
            continue
        matched_features.add(feature.feature_id)
        for mapping in mapped_edges:
            matches.append(
                CurbMatch(
                    feature_id=feature.feature_id,
                    edge_id=mapping.edge_id,
                    edge_length_m=mapping.edge_length_m,
                    confidence=mapping.confidence,
                    distance_m=0.0,
                    strategy="direct_way",
                    curb_risk=feature.curb_risk,
                    observed_at=feature.observed_at,
                    highway=mapping.highway,
                    access=mapping.access,
                    source_tags=feature.source_tags,
                )
            )
    return matches, {
        "direct_way_features": direct_features,
        "direct_matched_features": len(matched_features),
        "direct_unmatched_features": unmatched_way_features,
        "excluded_point_or_node_features": excluded_point_features,
    }


def copy_feature_ids(conn: PgConnection, table_name: str, feature_ids: set[str]) -> None:
    with conn.cursor() as cursor:
        cursor.execute(f"CREATE TEMP TABLE {table_name} (feature_id TEXT PRIMARY KEY) ON COMMIT DROP")
        if not feature_ids:
            return
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        for feature_id in sorted(feature_ids):
            writer.writerow([feature_id])
        buffer.seek(0)
        cursor.copy_expert(f"COPY {table_name} (feature_id) FROM STDIN WITH (FORMAT csv)", buffer)


def fetch_curb_sql_matches(conn: PgConnection, direct_matched_feature_ids: set[str]) -> tuple[list[CurbMatch], dict[str, Any]]:
    copy_feature_ids(conn, "osm_curb_direct_matched_features", direct_matched_feature_ids)
    matches: list[CurbMatch] = []
    stats: dict[str, Any] = {}
    with conn.cursor() as cursor:
        plausible_predicate = """
          lower(coalesce(edge.highway, '')) ~ '(footway|path|pedestrian|cycleway|steps|service|living_street|residential|crossing|track)'
          AND lower(coalesce(edge.access, '')) NOT IN ('no', 'private')
        """
        cursor.execute(
            f"""
            CREATE TEMP TABLE osm_curb_node_candidates AS
            WITH point_features AS (
              SELECT *
              FROM osm_advanced_features feature
              WHERE feature.factor = 'curb'
                AND feature.geometry_type = 'Point'
                AND NOT EXISTS (
                  SELECT 1 FROM osm_curb_direct_matched_features direct
                  WHERE direct.feature_id = feature.feature_id
                )
            ),
            nearest_nodes AS (
              SELECT
                feature.feature_id,
                feature.observed_at,
                feature.curb_risk,
                feature.source_tags,
                node.node_id,
                node.distance_m,
                row_number() OVER (
                  PARTITION BY feature.feature_id
                  ORDER BY node.distance_m, node.node_id
                ) AS rn,
                lead(node.distance_m) OVER (
                  PARTITION BY feature.feature_id
                  ORDER BY node.distance_m, node.node_id
                ) AS next_distance_m
              FROM point_features AS feature
              CROSS JOIN LATERAL (
                SELECT
                  node_id,
                  ST_Distance(geometry::geography, feature.geom::geography) AS distance_m
                FROM public.moscow_network_nodes
                WHERE geometry && ST_Expand(feature.geom, 3.0 / 75000.0)
                ORDER BY geometry <-> feature.geom
                LIMIT 2
              ) AS node
              WHERE node.distance_m <= 3.0
            ),
            nearest_unambiguous AS (
              SELECT *
              FROM nearest_nodes
              WHERE rn = 1
                AND (next_distance_m IS NULL OR (next_distance_m - distance_m) >= 1.0)
            ),
            connected_edges AS (
              SELECT
                node.feature_id,
                node.observed_at,
                node.curb_risk,
                node.source_tags,
                node.distance_m,
                edge.id AS edge_id,
                COALESCE(NULLIF(edge.length, 0), ST_Length(edge.geometry::geography)) AS edge_length_m,
                COALESCE(edge.highway, '') AS highway,
                COALESCE(edge.access, '') AS access,
                count(*) OVER (PARTITION BY node.feature_id) AS connected_edge_count
              FROM nearest_unambiguous AS node
              JOIN public.moscow_network AS edge
                ON edge.u = node.node_id OR edge.v = node.node_id
              WHERE {plausible_predicate}
            )
            SELECT
              *,
              CASE
                WHEN connected_edge_count > 4 THEN true
                ELSE false
              END AS is_ambiguous,
              greatest(
                0.60,
                CASE WHEN distance_m <= 1.5 THEN 0.85 ELSE 0.75 END - ((connected_edge_count - 1) * 0.03)
              ) AS match_confidence
            FROM connected_edges
            """
        )
        cursor.execute(
            """
            CREATE TEMP TABLE osm_curb_node_accepted AS
            SELECT *
            FROM osm_curb_node_candidates
            WHERE is_ambiguous = false
            """
        )
        cursor.execute(
            """
            CREATE TEMP TABLE osm_curb_node_accepted_features AS
            SELECT DISTINCT feature_id FROM osm_curb_node_accepted
            """
        )
        cursor.execute(
            """
            SELECT
              count(DISTINCT feature_id) AS matched,
              count(DISTINCT feature_id) FILTER (WHERE is_ambiguous) AS ambiguous,
              (SELECT count(DISTINCT feature_id) FROM osm_curb_node_accepted) AS accepted
            FROM osm_curb_node_candidates
            """
        )
        node_matched, node_ambiguous, node_accepted = [int(value or 0) for value in cursor.fetchone()]
        stats["node_neighborhood"] = {
            "matched_features": node_matched,
            "ambiguous_features": node_ambiguous,
            "accepted_features": node_accepted,
        }

        cursor.execute(
            f"""
            CREATE TEMP TABLE osm_curb_crossing_candidates AS
            WITH point_features AS (
              SELECT *
              FROM osm_advanced_features feature
              WHERE feature.factor = 'curb'
                AND feature.geometry_type = 'Point'
                AND NOT EXISTS (
                  SELECT 1 FROM osm_curb_direct_matched_features direct
                  WHERE direct.feature_id = feature.feature_id
                )
                AND NOT EXISTS (
                  SELECT 1 FROM osm_curb_node_accepted_features node_match
                  WHERE node_match.feature_id = feature.feature_id
                )
            ),
            active_crossing_edges AS (
              SELECT DISTINCT enrichment.edge_id
              FROM safety_edge_enrichment AS enrichment
              JOIN safety_enrichment_datasets AS dataset
                ON dataset.dataset_version = enrichment.dataset_version
              WHERE dataset.is_active = true
                AND (
                  enrichment.crossing_count IS NOT NULL
                  OR enrichment.crossing_risk IS NOT NULL
                )
            ),
            candidate_pool AS (
              SELECT
                feature.feature_id,
                feature.observed_at,
                feature.curb_risk,
                feature.source_tags,
                edge.id AS edge_id,
                COALESCE(NULLIF(edge.length, 0), ST_Length(edge.geometry::geography)) AS edge_length_m,
                COALESCE(edge.highway, '') AS highway,
                COALESCE(edge.access, '') AS access,
                edge.distance_m
              FROM point_features AS feature
              CROSS JOIN LATERAL (
                SELECT
                  edge.id,
                  edge.length,
                  edge.geometry,
                  edge.highway,
                  edge.access,
                  ST_Distance(edge.geometry::geography, feature.geom::geography) AS distance_m
                FROM public.moscow_network AS edge
                JOIN active_crossing_edges AS active_edge
                  ON active_edge.edge_id = edge.id
                WHERE edge.geometry && ST_Expand(feature.geom, 3.0 / 75000.0)
                  AND {plausible_predicate}
                ORDER BY edge.geometry <-> feature.geom
                LIMIT 2
              ) AS edge
              WHERE edge.distance_m <= 3.0
            ),
            ranked AS (
              SELECT
                candidate_pool.*,
                row_number() OVER (
                  PARTITION BY candidate_pool.feature_id
                  ORDER BY candidate_pool.distance_m, candidate_pool.edge_id
                ) AS rn,
                lead(candidate_pool.distance_m) OVER (
                  PARTITION BY candidate_pool.feature_id
                  ORDER BY candidate_pool.distance_m, candidate_pool.edge_id
                ) AS next_distance_m
              FROM candidate_pool
            )
            SELECT
              *,
              CASE
                WHEN rn != 1 THEN true
                WHEN next_distance_m IS NOT NULL AND (next_distance_m - distance_m) < 1.0 THEN true
                ELSE false
              END AS is_ambiguous,
              CASE WHEN distance_m <= 1.5 THEN 0.80 ELSE 0.65 END AS match_confidence
            FROM ranked
            WHERE rn = 1
            """
        )
        cursor.execute(
            """
            CREATE TEMP TABLE osm_curb_crossing_accepted AS
            SELECT *
            FROM osm_curb_crossing_candidates
            WHERE is_ambiguous = false
            """
        )
        cursor.execute(
            """
            CREATE TEMP TABLE osm_curb_crossing_accepted_features AS
            SELECT DISTINCT feature_id FROM osm_curb_crossing_accepted
            """
        )
        cursor.execute(
            """
            SELECT
              count(DISTINCT feature_id) AS matched,
              count(DISTINCT feature_id) FILTER (WHERE is_ambiguous) AS ambiguous,
              (SELECT count(DISTINCT feature_id) FROM osm_curb_crossing_accepted) AS accepted
            FROM osm_curb_crossing_candidates
            """
        )
        crossing_matched, crossing_ambiguous, crossing_accepted = [int(value or 0) for value in cursor.fetchone()]
        stats["crossing_assisted"] = {
            "matched_features": crossing_matched,
            "ambiguous_features": crossing_ambiguous,
            "accepted_features": crossing_accepted,
        }

        cursor.execute(
            f"""
            CREATE TEMP TABLE osm_curb_line_candidates AS
            WITH line_features AS (
              SELECT *
              FROM osm_advanced_features feature
              WHERE feature.factor = 'curb'
                AND feature.geometry_type != 'Point'
                AND NOT EXISTS (
                  SELECT 1 FROM osm_curb_direct_matched_features direct
                  WHERE direct.feature_id = feature.feature_id
                )
            ),
            candidate_pool AS (
              SELECT
                feature.feature_id,
                feature.observed_at,
                feature.curb_risk,
                feature.source_tags,
                edge.id AS edge_id,
                COALESCE(NULLIF(edge.length, 0), ST_Length(edge.geometry::geography)) AS edge_length_m,
                COALESCE(edge.highway, '') AS highway,
                COALESCE(edge.access, '') AS access,
                edge.distance_m
              FROM line_features AS feature
              CROSS JOIN LATERAL (
                SELECT
                  id,
                  length,
                  geometry,
                  highway,
                  access,
                  ST_Distance(geometry::geography, feature.geom::geography) AS distance_m
                FROM public.moscow_network AS edge
                WHERE edge.geometry && ST_Expand(feature.geom, 3.0 / 75000.0)
                  AND {plausible_predicate}
                ORDER BY edge.geometry <-> ST_PointOnSurface(feature.geom)
                LIMIT 2
              ) AS edge
              WHERE edge.distance_m <= 3.0
            ),
            ranked AS (
              SELECT
                candidate_pool.*,
                row_number() OVER (
                  PARTITION BY candidate_pool.feature_id
                  ORDER BY candidate_pool.distance_m, candidate_pool.edge_id
                ) AS rn,
                lead(candidate_pool.distance_m) OVER (
                  PARTITION BY candidate_pool.feature_id
                  ORDER BY candidate_pool.distance_m, candidate_pool.edge_id
                ) AS next_distance_m
              FROM candidate_pool
            )
            SELECT
              *,
              CASE
                WHEN rn != 1 THEN true
                WHEN next_distance_m IS NOT NULL AND (next_distance_m - distance_m) < 1.0 THEN true
                ELSE false
              END AS is_ambiguous,
              CASE WHEN distance_m <= 1.5 THEN 0.75 ELSE 0.65 END AS match_confidence
            FROM ranked
            WHERE rn = 1
            """
        )
        cursor.execute(
            """
            CREATE TEMP TABLE osm_curb_line_accepted AS
            SELECT *
            FROM osm_curb_line_candidates
            WHERE is_ambiguous = false
            """
        )
        cursor.execute(
            """
            SELECT
              count(DISTINCT feature_id) AS matched,
              count(DISTINCT feature_id) FILTER (WHERE is_ambiguous) AS ambiguous,
              (SELECT count(DISTINCT feature_id) FROM osm_curb_line_accepted) AS accepted
            FROM osm_curb_line_candidates
            """
        )
        line_matched, line_ambiguous, line_accepted = [int(value or 0) for value in cursor.fetchone()]
        stats["spatial_line"] = {
            "matched_features": line_matched,
            "ambiguous_features": line_ambiguous,
            "accepted_features": line_accepted,
        }

        cursor.execute(
            """
            SELECT
              feature_id,
              edge_id,
              edge_length_m,
              match_confidence,
              distance_m,
              'node_neighborhood' AS strategy,
              curb_risk,
              COALESCE(observed_at::TEXT, '') AS observed_at,
              highway,
              access,
              source_tags::TEXT
            FROM osm_curb_node_accepted
            UNION ALL
            SELECT
              feature_id,
              edge_id,
              edge_length_m,
              match_confidence,
              distance_m,
              'crossing_assisted' AS strategy,
              curb_risk,
              COALESCE(observed_at::TEXT, '') AS observed_at,
              highway,
              access,
              source_tags::TEXT
            FROM osm_curb_crossing_accepted
            UNION ALL
            SELECT
              feature_id,
              edge_id,
              edge_length_m,
              match_confidence,
              distance_m,
              'spatial_line' AS strategy,
              curb_risk,
              COALESCE(observed_at::TEXT, '') AS observed_at,
              highway,
              access,
              source_tags::TEXT
            FROM osm_curb_line_accepted
            ORDER BY strategy, feature_id, edge_id
            """
        )
        for row in cursor.fetchall():
            feature_id, edge_id, edge_length_m, confidence, distance_m, strategy, curb_risk, observed_at, highway, access, source_tags = row
            matches.append(
                CurbMatch(
                    feature_id=str(feature_id),
                    edge_id=int(edge_id),
                    edge_length_m=float(edge_length_m or 0.0),
                    confidence=float(confidence or 0.0),
                    distance_m=float(distance_m) if distance_m is not None else None,
                    strategy=str(strategy),
                    curb_risk=float(curb_risk),
                    observed_at=str(observed_at or ""),
                    highway=str(highway or ""),
                    access=str(access or ""),
                    source_tags=json.loads(source_tags or "{}"),
                )
            )
    return matches, stats


def write_curb_matches_csv(matches: list[CurbMatch], output_path: Path) -> tuple[dict[str, int], float | None]:
    rows_by_edge: dict[int, dict[str, Any]] = {}
    for match in matches:
        state = rows_by_edge.setdefault(
            match.edge_id,
            {
                "confidence_values": [],
                "observed_at": "",
                "edge_length_m": match.edge_length_m,
                "curb_risks": [],
                "curb_frequency": 0,
            },
        )
        state["confidence_values"].append(match.confidence)
        if match.observed_at and match.observed_at > state["observed_at"]:
            state["observed_at"] = match.observed_at
        state["curb_risks"].append(match.curb_risk)
        state["curb_frequency"] += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for edge_id, state in sorted(rows_by_edge.items()):
        curb_risks = state["curb_risks"]
        if not curb_risks:
            continue
        confidence_values = state["confidence_values"]
        edge_length_km = max(float(state["edge_length_m"] or 0.0) / 1000.0, 0.001)
        curb_frequency = int(state["curb_frequency"])
        row = {column: "" for column in CSV_COLUMNS}
        row.update(
            {
                "edge_id": str(edge_id),
                "confidence": str(round(sum(confidence_values) / len(confidence_values), 3)),
                "observed_at": state["observed_at"],
                "curb_risk": str(round(sum(curb_risks) / len(curb_risks), 3)),
                "curb_frequency": str(curb_frequency),
                "curb_density_per_km": str(round(curb_frequency / edge_length_km, 3)),
            }
        )
        rows.append(row)

    with output_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    factor_counts, avg_confidence = summarize_csv(output_path)
    return factor_counts, avg_confidence


def source_audit(raw_features: Iterable[dict[str, Any]], normalized: list[OsmFeature], factor: str) -> dict[str, Any]:
    geometry_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    normalized_geometry_counts: Counter[str] = Counter(feature.geometry_type for feature in normalized)
    audit_keys = (
        "kerb",
        "kerb:left",
        "kerb:right",
        "kerb:height",
        "crossing:kerb",
        "sidewalk:left:kerb",
        "sidewalk:right:kerb",
        "barrier=kerb",
        "highway=kerb",
        "sloped_curb",
        "ramp:kerb",
        "kerb:ramp",
        "tactile_paving",
        "wheelchair",
        "ramp",
    )
    for raw_feature in raw_features:
        geometry = raw_feature.get("geometry") if isinstance(raw_feature, dict) else None
        properties = raw_feature.get("properties") if isinstance(raw_feature, dict) else None
        if isinstance(geometry, dict):
            geometry_counts[str(geometry.get("type") or "unknown")] += 1
        if not isinstance(properties, dict):
            continue
        for key in audit_keys:
            if "=" in key:
                tag_key, tag_value = key.split("=", 1)
                if str(properties.get(tag_key, "")).strip().lower() == tag_value:
                    tag_counts[key] += 1
            elif key in properties:
                tag_counts[key] += 1
    return {
        "factor": factor,
        "raw_feature_count": sum(geometry_counts.values()),
        "raw_geometry_counts": dict(sorted(geometry_counts.items())),
        "normalized_feature_count": len(normalized),
        "normalized_geometry_counts": dict(sorted(normalized_geometry_counts.items())),
        "tag_counts": dict(sorted(tag_counts.items())),
        "supporting_tags_policy": "tactile_paving, wheelchair, and generic ramp tags are audited but do not create curb risk without a curb/kerb/ramp-to-kerb signal.",
    }


def curb_hybrid_mapping_and_write_csv(
    conn: PgConnection,
    features: list[OsmFeature],
    output_path: Path,
) -> dict[str, Any]:
    way_mapping = load_way_edge_mapping(conn)
    direct_matches, direct_stats = direct_curb_matches(features, way_mapping)
    direct_matched_feature_ids = {match.feature_id for match in direct_matches}
    sql_matches, strategy_stats = fetch_curb_sql_matches(conn, direct_matched_feature_ids)
    matches = direct_matches + sql_matches
    factor_counts, avg_confidence = write_curb_matches_csv(matches, output_path)

    accepted_feature_ids = {match.feature_id for match in matches}
    ambiguous_features = sum(int(strategy.get("ambiguous_features", 0)) for strategy in strategy_stats.values())
    distances = [match.distance_m for match in matches if match.distance_m is not None]
    distance_values = [float(distance) for distance in distances]
    incompatible_matches = [match for match in matches if is_incompatible_curb_edge(match.highway)]
    plausible_matches = [match for match in matches if is_plausible_curb_edge(match.highway, match.access)]
    strategy_counts = Counter(match.strategy for match in matches)
    sample_matches = [
        {
            "feature_id": match.feature_id,
            "edge_id": match.edge_id,
            "distance_m": None if match.distance_m is None else round(match.distance_m, 3),
            "strategy": match.strategy,
            "confidence": round(match.confidence, 3),
            "curb_risk": round(match.curb_risk, 3),
            "highway": match.highway,
            "access": match.access,
            "source_tags": match.source_tags,
        }
        for match in sorted(matches, key=lambda item: (item.strategy, item.feature_id, item.edge_id))[:20]
    ]
    matched_feature_count = len(accepted_feature_ids)
    with output_path.open(encoding="utf-8") as handle:
        import_rows = max(0, sum(1 for _ in handle) - 1)
    return {
        "features": len(features),
        "direct_way_features": direct_stats["direct_way_features"],
        "excluded_point_or_node_features": 0,
        "matched_features": matched_feature_count,
        "accepted_features": matched_feature_count,
        "unmatched_features": max(0, len(features) - matched_feature_count - ambiguous_features),
        "ambiguous_features": ambiguous_features,
        "ambiguous_rate": round(ambiguous_features / max(matched_feature_count + ambiguous_features, 1), 4),
        "import_rows": import_rows,
        "avg_confidence": avg_confidence,
        "factor_counts": factor_counts,
        "strategy_stats": {
            "direct_way": {
                "matched_features": direct_stats["direct_matched_features"],
                "ambiguous_features": 0,
                "accepted_features": direct_stats["direct_matched_features"],
            },
            **strategy_stats,
        },
        "strategy_match_rows": dict(sorted(strategy_counts.items())),
        "median_distance_m": None if not distance_values else round(median(distance_values), 3),
        "p95_distance_m": None if percentile(distance_values, 0.95) is None else round(float(percentile(distance_values, 0.95)), 3),
        "plausible_edge_rate": round(len(plausible_matches) / len(matches), 4) if matches else 0.0,
        "incompatible_edge_rate": round(len(incompatible_matches) / len(matches), 4) if matches else 1.0,
        "sample_matches": sample_matches,
    }


def spatial_join_and_write_csv(conn: PgConnection, output_path: Path, factor: str) -> dict[str, Any]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            CREATE TEMP TABLE osm_advanced_candidates AS
            WITH candidate_pool AS (
              SELECT
                feature.feature_id,
                feature.factor,
                feature.geometry_type,
                feature.observed_at,
                feature.curb_risk,
                feature.crossing_risk,
                feature.controlled_crossing_count,
                feature.uncontrolled_crossing_count,
                edge.id AS edge_id,
                COALESCE(NULLIF(edge.length, 0), ST_Length(edge.geometry::geography)) AS edge_length_m,
                edge.distance_m
              FROM osm_advanced_features AS feature
              CROSS JOIN LATERAL (
                SELECT
                  id,
                  geometry,
                  length,
                  ST_Distance(geometry::geography, feature.geom::geography) AS distance_m
                FROM public.moscow_network
                WHERE geometry && ST_Expand(feature.geom, feature.threshold_m / 75000.0)
                ORDER BY geometry <-> ST_PointOnSurface(feature.geom)
                LIMIT 8
              ) AS edge
              WHERE edge.distance_m <= feature.threshold_m
            ),
            candidates AS (
              SELECT
                candidate_pool.*,
                row_number() OVER (
                  PARTITION BY candidate_pool.feature_id
                  ORDER BY candidate_pool.distance_m, candidate_pool.edge_id
                ) AS rn,
                lead(candidate_pool.distance_m) OVER (
                  PARTITION BY candidate_pool.feature_id
                  ORDER BY candidate_pool.distance_m, candidate_pool.edge_id
                ) AS next_distance_m
              FROM candidate_pool
            )
            SELECT *
            FROM candidates
            """
        )
        cursor.execute(
            """
            CREATE TEMP TABLE osm_advanced_matches AS
            SELECT
              *,
              CASE
                WHEN next_distance_m IS NOT NULL AND (next_distance_m - distance_m) < 1.0 THEN true
                ELSE false
              END AS is_ambiguous,
              CASE
                WHEN geometry_type = 'Point' AND distance_m <= 3.0 THEN 0.90
                WHEN geometry_type = 'Point' THEN 0.70
                ELSE 0.85
              END AS match_confidence
            FROM osm_advanced_candidates
            WHERE rn = 1
            """
        )
        cursor.execute(
            """
            CREATE TEMP TABLE osm_advanced_accepted AS
            SELECT *
            FROM osm_advanced_matches
            WHERE is_ambiguous = false
            """
        )
        cursor.execute(
            """
            SELECT
              (SELECT count(*) FROM osm_advanced_features) AS features,
              (SELECT count(*) FROM osm_advanced_matches) AS matched,
              (SELECT count(*) FROM osm_advanced_matches WHERE is_ambiguous) AS ambiguous,
              (SELECT count(*) FROM osm_advanced_accepted) AS accepted
            """
        )
        feature_count, matched_count, ambiguous_count, accepted_count = [int(value or 0) for value in cursor.fetchone()]
        unmatched_count = max(0, feature_count - matched_count)
        ambiguous_rate = round(ambiguous_count / matched_count, 4) if matched_count else 1.0

        output_path.parent.mkdir(parents=True, exist_ok=True)
        rows: list[dict[str, str]] = []
        if factor == "curb":
            cursor.execute(
                """
                SELECT
                  edge_id,
                  round(avg(match_confidence)::numeric, 3)::TEXT AS confidence,
                  max(observed_at)::TEXT AS observed_at,
                  round(avg(curb_risk)::numeric, 3)::TEXT AS curb_risk,
                  count(*)::TEXT AS curb_frequency,
                  round((count(*) / NULLIF(max(edge_length_m) / 1000.0, 0))::numeric, 3)::TEXT AS curb_density_per_km
                FROM osm_advanced_accepted
                GROUP BY edge_id
                ORDER BY edge_id
                """
            )
            for edge_id, confidence, observed_at, curb_risk, curb_frequency, curb_density in cursor.fetchall():
                row = {column: "" for column in CSV_COLUMNS}
                row.update(
                    {
                        "edge_id": str(edge_id),
                        "confidence": confidence,
                        "observed_at": observed_at or "",
                        "curb_risk": curb_risk,
                        "curb_frequency": curb_frequency,
                        "curb_density_per_km": curb_density,
                    }
                )
                rows.append(row)
        else:
            cursor.execute(
                """
                SELECT
                  edge_id,
                  round(avg(match_confidence)::numeric, 3)::TEXT AS confidence,
                  max(observed_at)::TEXT AS observed_at,
                  count(*)::TEXT AS crossing_count,
                  sum(COALESCE(controlled_crossing_count, 0))::TEXT AS controlled_crossing_count,
                  sum(COALESCE(uncontrolled_crossing_count, 0))::TEXT AS uncontrolled_crossing_count,
                  round(avg(crossing_risk)::numeric, 3)::TEXT AS crossing_risk
                FROM osm_advanced_accepted
                GROUP BY edge_id
                ORDER BY edge_id
                """
            )
            for edge_id, confidence, observed_at, crossing_count, controlled_count, uncontrolled_count, crossing_risk in cursor.fetchall():
                row = {column: "" for column in CSV_COLUMNS}
                row.update(
                    {
                        "edge_id": str(edge_id),
                        "confidence": confidence,
                        "observed_at": observed_at or "",
                        "crossing_count": crossing_count,
                        "controlled_crossing_count": controlled_count,
                        "uncontrolled_crossing_count": uncontrolled_count,
                        "crossing_risk": crossing_risk,
                    }
                )
                rows.append(row)

        with output_path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    return {
        "matched_features": matched_count,
        "accepted_features": accepted_count,
        "unmatched_features": unmatched_count,
        "ambiguous_features": ambiguous_count,
        "ambiguous_rate": ambiguous_rate,
        "import_rows": len(rows),
    }


def summarize_csv(output_path: Path) -> tuple[dict[str, int], float | None]:
    factor_counts: Counter[str] = Counter()
    confidence_total = 0.0
    confidence_count = 0
    with output_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            for column in CSV_COLUMNS:
                if column in {"edge_id", "confidence", "observed_at"}:
                    continue
                if (row.get(column) or "").strip():
                    factor_counts[column] += 1
            confidence = (row.get("confidence") or "").strip()
            if confidence:
                confidence_total += float(confidence)
                confidence_count += 1
    avg_confidence = round(confidence_total / confidence_count, 3) if confidence_count else None
    return dict(sorted(factor_counts.items())), avg_confidence


def dataset_version_for(factor: str, latest_timestamp: str, explicit: str) -> str:
    if explicit:
        return explicit
    date_part = latest_timestamp[:10].replace("-", "") if latest_timestamp else datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"osm-moscow-oblast-{factor}-{date_part}"


def build(args: argparse.Namespace) -> dict[str, Any]:
    factor = args.factor
    osm_path = Path(args.osm_extract).resolve()
    output_path = Path(args.output).resolve()
    metadata_path = Path(args.metadata_output).resolve()
    if factor not in FILTERS:
        raise SystemExit(f"fail: unsupported advanced factor: {factor}")
    raw_features = run_osmium_geojsonseq(osm_path, args.osmium_bin, factor)
    features = normalized_features(raw_features, factor)
    if not features:
        raise SystemExit(f"fail: no real OSM {factor} features found in {osm_path}")
    audit = source_audit(raw_features, features, factor)

    conn = psycopg2.connect(args.database_url)
    try:
        if args.mapping_mode == "direct-ways":
            direct_counts = direct_way_mapping_and_write_csv(conn, features, output_path, factor)
            copied_counts = {
                "features": direct_counts["features"],
                "point_features": direct_counts["excluded_point_or_node_features"],
                "line_features": direct_counts["direct_way_features"],
            }
            join_counts = direct_counts
        elif args.mapping_mode == "curb-hybrid":
            if factor != "curb":
                raise SystemExit("fail: curb-hybrid mapping mode is only supported for factor=curb")
            copied_counts = copy_features(conn, features, factor)
            join_counts = curb_hybrid_mapping_and_write_csv(conn, features, output_path)
        else:
            copied_counts = copy_features(conn, features, factor)
            join_counts = spatial_join_and_write_csv(conn, output_path, factor)
    finally:
        conn.close()

    factor_counts, avg_confidence = summarize_csv(output_path)
    latest_timestamp = max((feature.observed_at for feature in features if feature.observed_at), default="")
    osm_sha256 = sha256_file(osm_path)
    csv_sha256 = sha256_file(output_path)
    min_matches = args.min_matches
    distance_gate_passed = (
        factor != "curb"
        or args.mapping_mode != "curb-hybrid"
        or (
            join_counts.get("p95_distance_m") is not None
            and float(join_counts["p95_distance_m"]) <= args.max_p95_distance_m
            and (
                join_counts.get("median_distance_m") is None
                or float(join_counts["median_distance_m"]) <= args.max_median_distance_m
            )
        )
    )
    plausible_edge_rate = join_counts.get("plausible_edge_rate")
    incompatible_edge_rate = join_counts.get("incompatible_edge_rate")
    min_import_rows = args.min_import_rows if factor == "curb" else 0
    plausible_gate_passed = (
        factor != "curb"
        or args.mapping_mode != "curb-hybrid"
        or (
            float(plausible_edge_rate if plausible_edge_rate is not None else 0.0) >= args.min_plausible_edge_rate
            and float(incompatible_edge_rate if incompatible_edge_rate is not None else 1.0) <= args.max_incompatible_edge_rate
        )
    )
    import_row_gate_passed = join_counts["import_rows"] >= min_import_rows
    validation_passed = (
        join_counts["accepted_features"] >= min_matches
        and import_row_gate_passed
        and join_counts["ambiguous_rate"] <= args.max_ambiguous_rate
        and distance_gate_passed
        and plausible_gate_passed
        and bool(factor_counts)
    )
    dataset_version = dataset_version_for(factor, latest_timestamp, args.dataset_version)
    metadata = {
        "dataset_version": dataset_version,
        "dataset_name": f"OpenStreetMap Moscow Oblast {factor} enrichment",
        "source_name": f"OpenStreetMap {factor} tags via Geofabrik Central Federal District extract",
        "source_url": args.source_url,
        "source_references": {
            "osm_copyright": OSM_COPYRIGHT_URL,
            "kerb": OSM_KERB_DOCS,
            "crossings": OSM_CROSSING_DOCS,
            "footway_crossing": OSM_FOOTWAY_CROSSING_DOCS,
            "traffic_signals": OSM_TRAFFIC_SIGNALS_DOCS,
        },
        "license": "Open Database License (ODbL) 1.0; attribution required",
        "source_file": str(osm_path),
        "source_sha256": f"sha256:{osm_sha256}",
        "generated_csv": str(output_path),
        "generated_csv_sha256": f"sha256:{csv_sha256}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "latest_osm_timestamp": latest_timestamp,
        "mapping_method": (
            "direct public.moscow_network.osmid to OSM way id; point/node features are not guessed"
            if args.mapping_mode == "direct-ways"
            else "hybrid curb mapping: direct OSM way ids, nearest graph node within 3m to connected plausible edges, "
            "crossing-assisted point mapping within 3m, and line spatial join within 3m; ambiguous matches rejected"
            if args.mapping_mode == "curb-hybrid"
            else "audited spatial join to public.moscow_network: point features nearest edge within 8m "
            "(0.90 confidence within 3m, 0.70 within 8m); line features nearest/intersecting edge within 5m "
            "(0.85 confidence); top-two matches closer than 1m are rejected as ambiguous"
        ),
        "mapping_mode": args.mapping_mode,
        "enabled_factors": [factor],
        "source_audit": audit,
        "feature_counts": copied_counts,
        "matched_features": join_counts["matched_features"],
        "accepted_features": join_counts["accepted_features"],
        "unmatched_features": join_counts["unmatched_features"],
        "excluded_point_or_node_features": join_counts.get("excluded_point_or_node_features", 0),
        "ambiguous_features": join_counts["ambiguous_features"],
        "ambiguous_rate": join_counts["ambiguous_rate"],
        "median_distance_m": join_counts.get("median_distance_m"),
        "p95_distance_m": join_counts.get("p95_distance_m"),
        "plausible_edge_rate": join_counts.get("plausible_edge_rate"),
        "incompatible_edge_rate": join_counts.get("incompatible_edge_rate"),
        "strategy_stats": join_counts.get("strategy_stats", {}),
        "strategy_match_rows": join_counts.get("strategy_match_rows", {}),
        "sample_matches": join_counts.get("sample_matches", []),
        "import_rows": join_counts["import_rows"],
        "avg_confidence": avg_confidence,
        "factor_counts": factor_counts,
        "validation": {
            "passed": validation_passed,
            "min_matches": min_matches,
            "min_import_rows": min_import_rows if factor == "curb" else None,
            "max_ambiguous_rate": args.max_ambiguous_rate,
            "max_p95_distance_m": args.max_p95_distance_m if factor == "curb" else None,
            "max_median_distance_m": args.max_median_distance_m if factor == "curb" else None,
            "min_plausible_edge_rate": args.min_plausible_edge_rate if factor == "curb" else None,
            "max_incompatible_edge_rate": args.max_incompatible_edge_rate if factor == "curb" else None,
            "import_row_gate_passed": import_row_gate_passed,
            "distance_gate_passed": distance_gate_passed,
            "plausible_gate_passed": plausible_gate_passed,
            "activation_policy": "activate only when validation passed and provenance metadata is present",
        },
        "inactive_factors": {
            "traffic_intensity": "No measured traffic source is imported by this OSM curb/crossing pipeline.",
            "pedestrian_density": "No legal pedestrian density source is imported.",
            "micromobility_forbidden_zones": "Official zone polygons are not imported.",
            "micromobility_slow_zones": "Official slow-zone polygons are not imported.",
            "weather_risk": "Weather is dynamic and handled by the optional provider, not this static OSM import.",
            "telemetry_confidence": "No real telemetry samples are imported.",
        },
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False))
    if not validation_passed and args.fail_on_validation_error:
        return_code = 1
        print(f"fail: OSM {factor} validation did not pass; dataset was not activation-ready", file=sys.stderr)
        raise SystemExit(return_code)
    return metadata


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--osm-extract", required=True)
    parser.add_argument("--factor", choices=sorted(FILTERS), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--metadata-output", required=True)
    parser.add_argument("--dataset-version", default="")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--psql-bin", default="psql")
    parser.add_argument("--osmium-bin", default="osmium")
    parser.add_argument("--min-matches", type=int, default=1000)
    parser.add_argument("--min-import-rows", type=int, default=1000)
    parser.add_argument("--max-ambiguous-rate", type=float, default=0.15)
    parser.add_argument("--mapping-mode", choices=["direct-ways", "spatial", "curb-hybrid"], default="direct-ways")
    parser.add_argument("--max-p95-distance-m", type=float, default=5.0)
    parser.add_argument("--max-median-distance-m", type=float, default=2.5)
    parser.add_argument("--min-plausible-edge-rate", type=float, default=0.90)
    parser.add_argument("--max-incompatible-edge-rate", type=float, default=0.05)
    parser.add_argument("--fail-on-validation-error", action="store_true")
    args = parser.parse_args(argv)
    _ = args.psql_bin
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
