#!/usr/bin/env python3
"""Validate future measured traffic and pedestrian-density imports.

This script intentionally accepts only measured, edge-mapped rows. It does not
infer traffic from OSM road class/maxspeed/lanes and does not infer pedestrian
density from POIs, transit stations, or land-use proxies.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

ENRICHMENT_COLUMNS = [
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

TRAFFIC_RAW_FIELDS = ("traffic_volume", "speed_kmh", "congestion_index")
PEDESTRIAN_RAW_FIELDS = ("pedestrian_count", "pedestrian_flow", "density_value")
TRAFFIC_BLOCKED_TOKENS = {
    "accident",
    "crash",
    "dtp",
    "highway",
    "lanes",
    "maxspeed",
    "openstreetmap",
    "osm",
    "road_class",
    "road_exposure",
    "road_exposure_proxy",
}
PEDESTRIAN_BLOCKED_TOKENS = {
    "land_use",
    "poi",
    "proxy",
    "station",
    "transit",
}
PROVENANCE_COLUMNS = (
    "source_category",
    "source_basis",
    "input_type",
    "proxy_type",
    "measurement_type",
    "source_method",
)


def fail(row_number: int | None, message: str) -> None:
    prefix = f"fail: row {row_number}: " if row_number is not None else "fail: "
    raise SystemExit(f"{prefix}{message}")


def finite_float(row_number: int, value: str, label: str, *, min_value: float | None = None, max_value: float | None = None) -> float:
    raw = value.strip()
    if raw == "":
        fail(row_number, f"{label} is required")
    try:
        parsed = float(raw)
    except ValueError:
        fail(row_number, f"{label} must be numeric")
    if not math.isfinite(parsed):
        fail(row_number, f"{label} must be finite")
    if min_value is not None and parsed < min_value:
        fail(row_number, f"{label} must be >= {min_value}")
    if max_value is not None and parsed > max_value:
        fail(row_number, f"{label} must be <= {max_value}")
    return parsed


def optional_finite_float(row_number: int, value: str, label: str) -> float | None:
    raw = value.strip()
    if raw == "":
        return None
    try:
        parsed = float(raw)
    except ValueError:
        fail(row_number, f"{label} must be numeric")
    if not math.isfinite(parsed):
        fail(row_number, f"{label} must be finite")
    return parsed


def required_edge_id(row_number: int, value: str) -> int:
    raw = value.strip()
    if raw == "":
        fail(row_number, "edge_id is required")
    try:
        parsed = int(raw)
    except ValueError:
        fail(row_number, "edge_id must be an integer")
    if parsed < 1:
        fail(row_number, "edge_id must be >= 1")
    return parsed


def require_timestamp(row_number: int, row: dict[str, str]) -> str:
    observed_at = (row.get("observed_at") or "").strip()
    time_bucket = (row.get("time_bucket") or "").strip()
    timestamp = observed_at or time_bucket
    if not timestamp:
        fail(row_number, "observed_at or time_bucket is required")
    if timestamp.endswith("Z"):
        parse_target = f"{timestamp[:-1]}+00:00"
    else:
        parse_target = timestamp
    try:
        datetime.fromisoformat(parse_target)
    except ValueError:
        fail(row_number, "observed_at/time_bucket must be ISO-8601")
    return timestamp


def normalized_tokens(row: dict[str, str]) -> set[str]:
    tokens: set[str] = set()
    for column in PROVENANCE_COLUMNS:
        value = row.get(column)
        if not value:
            continue
        normalized = value.lower().replace("-", "_").replace("/", "_").replace(" ", "_")
        tokens.add(normalized)
        tokens.update(part for part in normalized.split("_") if part)
    return tokens


def reject_blocked_provenance(row_number: int, row: dict[str, str], blocked_tokens: set[str], label: str) -> None:
    matches = sorted(normalized_tokens(row) & blocked_tokens)
    if matches:
        fail(row_number, f"{label} cannot be activated from proxy/source tokens: {', '.join(matches)}")


def require_any_raw_field(row_number: int, row: dict[str, str], raw_fields: Iterable[str], label: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for field in raw_fields:
        parsed = optional_finite_float(row_number, row.get(field, ""), field)
        if parsed is not None:
            values[field] = parsed
    if not values:
        fail(row_number, f"{label} requires at least one measured raw field: {', '.join(raw_fields)}")
    return values


def validate_traffic_row(row_number: int, row: dict[str, str]) -> tuple[str, float, dict[str, float]]:
    reject_blocked_provenance(row_number, row, TRAFFIC_BLOCKED_TOKENS, "measured traffic")
    intensity = finite_float(row_number, row.get("traffic_intensity", ""), "traffic_intensity", min_value=0, max_value=1)
    raw_values = require_any_raw_field(row_number, row, TRAFFIC_RAW_FIELDS, "measured traffic")
    for raw_field, raw_value in raw_values.items():
        if raw_value < 0:
            fail(row_number, f"{raw_field} must be >= 0")
    return str(intensity), intensity, raw_values


def validate_pedestrian_row(row_number: int, row: dict[str, str]) -> tuple[str, float, dict[str, float]]:
    reject_blocked_provenance(row_number, row, PEDESTRIAN_BLOCKED_TOKENS, "pedestrian density")
    density = finite_float(row_number, row.get("pedestrian_density", ""), "pedestrian_density", min_value=0, max_value=1)
    raw_values = require_any_raw_field(row_number, row, PEDESTRIAN_RAW_FIELDS, "pedestrian density")
    for raw_field, raw_value in raw_values.items():
        if raw_value < 0:
            fail(row_number, f"{raw_field} must be >= 0")
    return str(density), density, raw_values


def validate_csv(layer: str, source_path: Path, target_path: Path, report_path: Path) -> dict[str, object]:
    if layer not in {"measured_traffic", "pedestrian_density"}:
        fail(None, "layer must be measured_traffic or pedestrian_density")

    target_factor = "traffic_intensity" if layer == "measured_traffic" else "pedestrian_density"
    required_factor = "traffic_intensity" if layer == "measured_traffic" else "pedestrian_density"

    with source_path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            fail(None, "source CSV is empty")
        missing = {"edge_id", "confidence", required_factor} - set(reader.fieldnames)
        if missing:
            fail(None, f"source CSV is missing required columns: {', '.join(sorted(missing))}")

        normalized_rows: list[dict[str, str]] = []
        confidences: list[float] = []
        values: list[float] = []
        raw_field_counts = {field: 0 for field in (TRAFFIC_RAW_FIELDS if layer == "measured_traffic" else PEDESTRIAN_RAW_FIELDS)}
        observed_values: list[str] = []

        for row_number, row in enumerate(reader, start=2):
            edge_id = required_edge_id(row_number, row.get("edge_id", ""))
            confidence = finite_float(row_number, row.get("confidence", ""), "confidence", min_value=0, max_value=1)
            observed_at = require_timestamp(row_number, row)
            if layer == "measured_traffic":
                factor_text, factor_value, raw_values = validate_traffic_row(row_number, row)
            else:
                factor_text, factor_value, raw_values = validate_pedestrian_row(row_number, row)

            for raw_field in raw_values:
                raw_field_counts[raw_field] += 1

            output_row = {column: "" for column in ENRICHMENT_COLUMNS}
            output_row.update(
                {
                    "edge_id": str(edge_id),
                    "confidence": str(confidence),
                    "observed_at": observed_at,
                    target_factor: factor_text,
                }
            )
            normalized_rows.append(output_row)
            confidences.append(confidence)
            values.append(factor_value)
            observed_values.append(observed_at)

    if not normalized_rows:
        fail(None, "source CSV has no data rows")

    with target_path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=ENRICHMENT_COLUMNS)
        writer.writeheader()
        writer.writerows(normalized_rows)

    report: dict[str, object] = {
        "layer": layer,
        "status": "validated",
        "row_count": len(normalized_rows),
        "active_factor": target_factor,
        "factor_counts": {target_factor: len(normalized_rows)},
        "avg_confidence": round(sum(confidences) / len(confidences), 6),
        "min_confidence": min(confidences),
        "max_confidence": max(confidences),
        "avg_value": round(sum(values) / len(values), 6),
        "min_observed_at": min(observed_values),
        "max_observed_at": max(observed_values),
        "raw_field_counts": raw_field_counts,
        "mapping_method": "source edge_id to public.moscow_network.id",
        "activation_policy": "requires real licensed measured source, checksum, version, timestamp, edge mapping, confidence, and explicit ACTIVATE_ENRICHMENT=true",
        "no_fake_policy": "OSM road attributes, POI/transit proxies, accident data, commercial leads without licensed export, and test fixtures must not be activated",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(
            "Usage: validate-measured-layer-csv.py measured_traffic|pedestrian_density source.csv normalized.csv report.json",
            file=sys.stderr,
        )
        return 2
    report = validate_csv(argv[1], Path(argv[2]), Path(argv[3]), Path(argv[4]))
    print(json.dumps({"status": "ok", "row_count": report["row_count"], "active_factor": report["active_factor"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
