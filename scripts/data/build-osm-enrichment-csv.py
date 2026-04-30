#!/usr/bin/env python3
"""Build a real edge-mapped SafeRoute enrichment CSV from local OSM way tags.

The join is deterministic: public.moscow_network.osmid -> OSM way id(s).
No spatial guessing is used here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_SOURCE_URL = "https://download.geofabrik.de/russia/central-fed-district.html"
OSM_TAG_FILTERS = (
    "w/surface",
    "w/smoothness",
    "w/sidewalk",
    "w/sidewalk:left",
    "w/sidewalk:right",
    "w/lit",
    "w/incline",
)

SURFACE_MAP = {
    "asphalt": "asphalt",
    "paving_stones": "paving_stones",
    "paving_stones:30": "paving_stones",
    "cobblestone": "cobblestone",
    "sett": "cobblestone",
    "unhewn_cobblestone": "cobblestone",
    "gravel": "gravel",
    "fine_gravel": "gravel",
    "dirt": "dirt",
    "earth": "dirt",
    "ground": "dirt",
    "mud": "dirt",
    "sand": "dirt",
    "grass": "dirt",
}
SURFACE_QUALITY_MAP = {
    "excellent": "smooth",
    "good": "smooth",
    "intermediate": "moderate",
    "bad": "broken",
    "very_bad": "broken",
    "horrible": "broken",
    "very_horrible": "broken",
    "impassable": "broken",
}
SIDEWALK_TRUE = {"yes", "both", "left", "right", "separate", "detached"}
SIDEWALK_FALSE = {"no", "none"}
LIGHTING_MAP = {
    "yes": "good",
    "24/7": "good",
    "automatic": "good",
    "half": "moderate",
    "limited": "moderate",
    "partial": "moderate",
    "no": "poor",
    "disused": "poor",
    "abandoned": "poor",
    "abadoned": "poor",
}
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
    "crossing_count",
    "lighting_quality",
    "slope_percent",
    "traffic_intensity",
    "pedestrian_density",
    "micromobility_allowed",
    "forbidden_zone",
    "weather_sensitive_risk",
    "telemetry_confidence",
]
FACTOR_COLUMNS = set(CSV_COLUMNS) - {"edge_id", "confidence", "observed_at"}
AMBIGUOUS = object()


@dataclass
class EdgeState:
    """Accumulated normalized factors for one graph edge."""

    way_count: int
    values: dict[str, str | object] = field(default_factory=dict)
    observed_at: str = ""
    matched_way_ids: set[str] = field(default_factory=set)
    source_tags: set[str] = field(default_factory=set)

    def add_value(self, column: str, value: str | None, way_id: str, tag_name: str, observed_at: str) -> None:
        if value is None or value == "":
            return
        current = self.values.get(column)
        if current is None:
            self.values[column] = value
        elif current != value:
            self.values[column] = AMBIGUOUS
        self.matched_way_ids.add(way_id)
        self.source_tags.add(tag_name)
        if observed_at and (not self.observed_at or observed_at > self.observed_at):
            self.observed_at = observed_at


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_text(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout


def load_graph_mapping(database_url: str, psql_bin: str) -> tuple[dict[str, list[int]], dict[int, int], int]:
    output = run_text(
        [
            psql_bin,
            database_url,
            "-Atqc",
            "SELECT id || '|' || osmid FROM public.moscow_network WHERE osmid IS NOT NULL;",
        ]
    )
    way_to_edges: dict[str, list[int]] = defaultdict(list)
    edge_way_count: dict[int, int] = {}
    edge_count = 0
    for line in output.splitlines():
        if "|" not in line:
            continue
        edge_id_raw, osmid = line.split("|", 1)
        edge_id = int(edge_id_raw)
        way_ids = sorted(set(re.findall(r"\d+", osmid)))
        if not way_ids:
            continue
        edge_count += 1
        edge_way_count[edge_id] = len(way_ids)
        for way_id in way_ids:
            way_to_edges[way_id].append(edge_id)
    return way_to_edges, edge_way_count, edge_count


def decode_opl_value(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return chr(int(match.group(1), 16))

    return re.sub(r"%([0-9A-Fa-f]{2})%", replace, value).strip().lower()


def parse_opl_tags(line: str) -> tuple[str, dict[str, str], str] | None:
    match = re.match(r"w(\d+)\s", line)
    if not match or " T" not in line:
        return None
    way_id = match.group(1)
    timestamp_match = re.search(r"\st([0-9TZ:.-]+)\s", line)
    observed_at = timestamp_match.group(1) if timestamp_match else ""
    tag_blob = line.split(" T", 1)[1].split(" N", 1)[0]
    tags: dict[str, str] = {}
    for pair in tag_blob.split(","):
        if "=" not in pair:
            continue
        key, raw_value = pair.split("=", 1)
        tags[key] = decode_opl_value(raw_value)
    return way_id, tags, observed_at


def sidewalk_presence(tags: dict[str, str]) -> str | None:
    value = tags.get("sidewalk")
    if value in SIDEWALK_TRUE:
        return "true"
    if value in SIDEWALK_FALSE:
        return "false"
    left = tags.get("sidewalk:left")
    right = tags.get("sidewalk:right")
    if left in SIDEWALK_TRUE or right in SIDEWALK_TRUE:
        return "true"
    if left in SIDEWALK_FALSE and right in SIDEWALK_FALSE:
        return "false"
    return None


def parse_incline(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.replace("%", "").strip()
    if normalized in {"up", "down", "yes", "no"} or "°" in normalized:
        return None
    if not re.fullmatch(r"-?\d+(\.\d+)?", normalized):
        return None
    parsed = float(normalized)
    if abs(parsed) > 40:
        return None
    return str(parsed)


def normalized_values(tags: dict[str, str], enabled_factors: set[str]) -> Iterable[tuple[str, str, str]]:
    if "surface" in enabled_factors:
        surface = SURFACE_MAP.get(tags.get("surface", ""))
        if surface:
            yield "surface_type", surface, "surface"
        smoothness = SURFACE_QUALITY_MAP.get(tags.get("smoothness", ""))
        if smoothness:
            yield "surface_quality", smoothness, "smoothness"
    if "sidewalk" in enabled_factors:
        sidewalk = sidewalk_presence(tags)
        if sidewalk is not None:
            yield "sidewalk_presence", sidewalk, "sidewalk"
    if "lighting" in enabled_factors:
        lighting = LIGHTING_MAP.get(tags.get("lit", ""))
        if lighting:
            yield "lighting_quality", lighting, "lit"
    if "slope" in enabled_factors:
        incline = parse_incline(tags.get("incline"))
        if incline is not None:
            yield "slope_percent", incline, "incline"


def extract_matching_osm_tags(osm_path: Path, osmium_bin: str) -> list[str]:
    with tempfile.NamedTemporaryFile(suffix=".opl") as handle:
        subprocess.run(
            [osmium_bin, "tags-filter", "-R", "-f", "opl", str(osm_path), *OSM_TAG_FILTERS, "-o", handle.name, "-O"],
            check=True,
        )
        handle.seek(0)
        return handle.read().decode("utf-8", errors="replace").splitlines()


def build_csv(args: argparse.Namespace) -> dict[str, object]:
    osm_path = Path(args.osm_extract).resolve()
    output_path = Path(args.output).resolve()
    metadata_path = Path(args.metadata_output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    way_to_edges, edge_way_count, graph_edges_with_osmid = load_graph_mapping(args.database_url, args.psql_bin)
    enabled_factors = {factor.strip() for factor in args.factors.split(",") if factor.strip()}
    unknown_factors = enabled_factors - {"surface", "sidewalk", "lighting", "slope"}
    if unknown_factors:
        raise SystemExit(f"fail: unsupported OSM enrichment factor(s): {', '.join(sorted(unknown_factors))}")
    if not enabled_factors:
        raise SystemExit("fail: at least one OSM enrichment factor must be enabled")
    edge_states = {edge_id: EdgeState(way_count=count) for edge_id, count in edge_way_count.items()}
    matched_way_ids: set[str] = set()
    source_value_counts: dict[str, Counter[str]] = defaultdict(Counter)
    ambiguous_counts: Counter[str] = Counter()

    for line in extract_matching_osm_tags(osm_path, args.osmium_bin):
        parsed = parse_opl_tags(line)
        if parsed is None:
            continue
        way_id, tags, observed_at = parsed
        edge_ids = way_to_edges.get(way_id)
        if not edge_ids:
            continue
        matched_way_ids.add(way_id)
        for column, value, tag_name in normalized_values(tags, enabled_factors):
            source_value_counts[column][value] += len(edge_ids)
            for edge_id in edge_ids:
                edge_states[edge_id].add_value(column, value, way_id, tag_name, observed_at)

    rows: list[dict[str, str]] = []
    factor_counts: Counter[str] = Counter()
    for edge_id, state in sorted(edge_states.items()):
        row = {column: "" for column in CSV_COLUMNS}
        row["edge_id"] = str(edge_id)
        row["observed_at"] = state.observed_at
        row["confidence"] = "0.8" if state.way_count > 1 else "0.9"
        has_factor = False
        for column in sorted(FACTOR_COLUMNS):
            value = state.values.get(column)
            if value is AMBIGUOUS:
                ambiguous_counts[column] += 1
                continue
            if isinstance(value, str) and value:
                row[column] = value
                factor_counts[column] += 1
                has_factor = True
        if has_factor:
            rows.append(row)

    with output_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    osm_sha256 = sha256_file(osm_path)
    csv_sha256 = sha256_file(output_path)
    latest_timestamp = max((row["observed_at"] for row in rows if row["observed_at"]), default="")
    avg_confidence = round(sum(float(row["confidence"]) for row in rows) / len(rows), 3) if rows else None
    route_data_date = latest_timestamp[:10].replace("-", "") if latest_timestamp else datetime.now(timezone.utc).strftime("%Y%m%d")
    factor_slug = "-".join(sorted(enabled_factors))
    default_dataset_version = (
        f"osm-moscow-oblast-tags-{route_data_date}"
        if factor_slug == "lighting-sidewalk-slope-surface"
        else f"osm-moscow-oblast-tags-{factor_slug}-{route_data_date}"
    )
    dataset_version = args.dataset_version or default_dataset_version
    metadata = {
        "dataset_version": dataset_version,
        "dataset_name": "OpenStreetMap Moscow Oblast way-tag enrichment",
        "source_name": "OpenStreetMap via Geofabrik Central Federal District extract",
        "source_url": args.source_url,
        "license": "Open Database License (ODbL) 1.0; attribution required",
        "source_file": str(osm_path),
        "source_sha256": f"sha256:{osm_sha256}",
        "generated_csv": str(output_path),
        "generated_csv_sha256": f"sha256:{csv_sha256}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "latest_osm_timestamp": latest_timestamp,
        "mapping_method": "direct public.moscow_network.osmid to OSM way id; no spatial guessing",
        "enabled_factors": sorted(enabled_factors),
        "graph_edges_with_osmid": graph_edges_with_osmid,
        "graph_way_ids": len(way_to_edges),
        "matched_osm_way_ids": len(matched_way_ids),
        "import_rows": len(rows),
        "avg_confidence": avg_confidence,
        "factor_counts": dict(sorted(factor_counts.items())),
        "ambiguous_factor_counts": dict(sorted(ambiguous_counts.items())),
        "source_value_counts": {key: dict(counter.most_common(20)) for key, counter in sorted(source_value_counts.items())},
        "confidence_policy": {
            "0.9": "single OSM way id maps directly to the SafeRoute graph edge",
            "0.8": "graph edge references multiple OSM way ids; conflicting factor values are omitted",
        },
        "inactive_factors": {
            "curb_risk": "OSM way tags in this pipeline do not provide reliable curb risk per edge.",
            "crossing_count": "OSM crossing tags are mostly node/geometry features and need a dedicated distinct-edge aggregation pipeline.",
            "traffic_intensity": "OSM maxspeed/lanes are graph attributes, not measured traffic intensity.",
            "pedestrian_density": "No real pedestrian density source is present.",
            "micromobility_forbidden_zones": "No legal zone polygon source is present.",
            "micromobility_slow_zones": "No legal zone polygon source is present.",
            "weather_risk": "No maintained weather-sensitive edge risk source is present.",
            "telemetry_confidence": "No real sidewalk telemetry samples are active.",
        },
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--osm-extract", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--metadata-output", required=True)
    parser.add_argument("--dataset-version", default="")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--factors", default="surface,sidewalk,lighting,slope")
    parser.add_argument("--psql-bin", default="psql")
    parser.add_argument("--osmium-bin", default="osmium")
    args = parser.parse_args(argv)
    metadata = build_csv(args)
    print(json.dumps(metadata, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
