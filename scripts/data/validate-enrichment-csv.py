#!/usr/bin/env python3
"""Validate and normalize real SafeRoute edge enrichment CSV files."""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

COLUMNS = [
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
SURFACE_TYPES = {"", "asphalt", "paving_stones", "cobblestone", "gravel", "dirt"}
SURFACE_QUALITIES = {"", "smooth", "moderate", "broken"}
LIGHTING_QUALITIES = {"", "poor", "moderate", "good"}
BOOL_VALUES = {"", "true", "false", "yes", "no", "1", "0"}


def fail(row_number: int, message: str) -> None:
    raise SystemExit(f"fail: row {row_number}: {message}")


def optional_float(row_number: int, value: str, label: str, *, min_value: float | None = None, max_value: float | None = None) -> str:
    raw = value.strip()
    if raw == "":
        return ""
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
    return str(parsed)


def optional_int(row_number: int, value: str, label: str, *, min_value: int | None = None) -> str:
    raw = value.strip()
    if raw == "":
        return ""
    try:
        parsed = int(raw)
    except ValueError:
        fail(row_number, f"{label} must be an integer")
    if min_value is not None and parsed < min_value:
        fail(row_number, f"{label} must be >= {min_value}")
    return str(parsed)


def optional_bool(row_number: int, value: str, label: str) -> str:
    raw = value.strip().lower()
    if raw not in BOOL_VALUES:
        fail(row_number, f"{label} must be one of true/false/yes/no/1/0")
    if raw in {"true", "yes", "1"}:
        return "true"
    if raw in {"false", "no", "0"}:
        return "false"
    return ""


def validate_csv(source_path: Path, target_path: Path) -> int:
    """Validate source CSV and write normalized rows for psql copy."""

    with source_path.open(newline="", encoding="utf-8") as source, target_path.open("w", newline="", encoding="utf-8") as target:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise SystemExit("fail: enrichment CSV is empty")
        missing = {"edge_id", "confidence"} - set(reader.fieldnames)
        if missing:
            raise SystemExit(f"fail: enrichment CSV is missing required columns: {', '.join(sorted(missing))}")

        writer = csv.DictWriter(target, fieldnames=COLUMNS)
        writer.writeheader()
        count = 0
        for row_number, row in enumerate(reader, start=2):
            edge_id = optional_int(row_number, row.get("edge_id", ""), "edge_id", min_value=1)
            if not edge_id:
                fail(row_number, "edge_id is required")
            confidence = optional_float(row_number, row.get("confidence", ""), "confidence", min_value=0, max_value=1)
            if not confidence:
                fail(row_number, "confidence is required")

            surface_type = row.get("surface_type", "").strip().lower()
            surface_quality = row.get("surface_quality", "").strip().lower()
            lighting_quality = row.get("lighting_quality", "").strip().lower()
            if surface_type not in SURFACE_TYPES:
                fail(row_number, "surface_type has unsupported value")
            if surface_quality not in SURFACE_QUALITIES:
                fail(row_number, "surface_quality has unsupported value")
            if lighting_quality not in LIGHTING_QUALITIES:
                fail(row_number, "lighting_quality has unsupported value")

            writer.writerow(
                {
                    "edge_id": edge_id,
                    "confidence": confidence,
                    "observed_at": row.get("observed_at", "").strip(),
                    "surface_type": surface_type,
                    "surface_quality": surface_quality,
                    "sidewalk_presence": optional_bool(row_number, row.get("sidewalk_presence", ""), "sidewalk_presence"),
                    "sidewalk_width_m": optional_float(row_number, row.get("sidewalk_width_m", ""), "sidewalk_width_m", min_value=0),
                    "curb_risk": optional_float(row_number, row.get("curb_risk", ""), "curb_risk", min_value=0, max_value=1),
                    "curb_frequency": optional_float(row_number, row.get("curb_frequency", ""), "curb_frequency", min_value=0),
                    "curb_density_per_km": optional_float(
                        row_number,
                        row.get("curb_density_per_km", ""),
                        "curb_density_per_km",
                        min_value=0,
                    ),
                    "crossing_count": optional_int(row_number, row.get("crossing_count", ""), "crossing_count", min_value=0),
                    "controlled_crossing_count": optional_int(
                        row_number,
                        row.get("controlled_crossing_count", ""),
                        "controlled_crossing_count",
                        min_value=0,
                    ),
                    "uncontrolled_crossing_count": optional_int(
                        row_number,
                        row.get("uncontrolled_crossing_count", ""),
                        "uncontrolled_crossing_count",
                        min_value=0,
                    ),
                    "crossing_risk": optional_float(row_number, row.get("crossing_risk", ""), "crossing_risk", min_value=0, max_value=1),
                    "lighting_quality": lighting_quality,
                    "slope_percent": optional_float(row_number, row.get("slope_percent", ""), "slope_percent"),
                    "traffic_intensity": optional_float(row_number, row.get("traffic_intensity", ""), "traffic_intensity", min_value=0, max_value=1),
                    "pedestrian_density": optional_float(row_number, row.get("pedestrian_density", ""), "pedestrian_density", min_value=0, max_value=1),
                    "micromobility_allowed": optional_bool(row_number, row.get("micromobility_allowed", ""), "micromobility_allowed"),
                    "forbidden_zone": optional_bool(row_number, row.get("forbidden_zone", ""), "forbidden_zone"),
                    "micromobility_slow_zone": optional_bool(
                        row_number,
                        row.get("micromobility_slow_zone", ""),
                        "micromobility_slow_zone",
                    ),
                    "zone_speed_limit_kmh": optional_float(
                        row_number,
                        row.get("zone_speed_limit_kmh", ""),
                        "zone_speed_limit_kmh",
                        min_value=0,
                    ),
                    "road_exposure_proxy": optional_float(
                        row_number,
                        row.get("road_exposure_proxy", ""),
                        "road_exposure_proxy",
                        min_value=0,
                        max_value=1,
                    ),
                    "weather_sensitive_risk": optional_float(row_number, row.get("weather_sensitive_risk", ""), "weather_sensitive_risk", min_value=0, max_value=1),
                    "telemetry_confidence": optional_float(row_number, row.get("telemetry_confidence", ""), "telemetry_confidence", min_value=0, max_value=1),
                }
            )
            count += 1

    if count == 0:
        raise SystemExit("fail: enrichment CSV has no data rows")
    return count


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: validate-enrichment-csv.py source.csv normalized.csv", file=sys.stderr)
        return 2
    count = validate_csv(Path(argv[1]), Path(argv[2]))
    print(count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
