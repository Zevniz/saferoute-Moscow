import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from test_scripts_static import ROOT, load_script_module


MODULE = load_script_module(
    "validate_micromobility_zones",
    ROOT / "scripts" / "data" / "validate-micromobility-zones.py",
)
FIXTURE = ROOT / "tests" / "fixtures" / "micromobility_zones" / "test-only-zones.geojson"


def write_geojson(path: Path, feature: dict) -> None:
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": [feature]}),
        encoding="utf-8",
    )


def test_test_only_fixture_normalizes_to_scored_zone_rows(tmp_path):
    normalized_csv = tmp_path / "zones.csv"
    report_path = tmp_path / "report.json"

    report = MODULE.normalize_geojson(FIXTURE, normalized_csv, report_path)

    csv_text = normalized_csv.read_text(encoding="utf-8")
    assert "test-forbidden-zone,forbidden" in csv_text
    assert "test-slow-zone,slow,15.0" in csv_text
    assert report["feature_count"] == 2
    assert report["scored_feature_count"] == 2
    assert report["zone_type_counts"]["forbidden"] == 1
    assert report["zone_type_counts"]["slow"] == 1


def test_zone_validator_rejects_missing_confidence(tmp_path):
    source = tmp_path / "missing-confidence.geojson"
    write_geojson(
        source,
        {
            "type": "Feature",
            "properties": {"zone_type": "forbidden"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[37.0, 55.0], [37.1, 55.0], [37.1, 55.1], [37.0, 55.1], [37.0, 55.0]]],
            },
        },
    )

    with pytest.raises(MODULE.ZoneValidationError, match="confidence is required"):
        MODULE.normalize_geojson(source, tmp_path / "zones.csv", tmp_path / "report.json")


def test_zone_validator_rejects_non_polygon_geometry(tmp_path):
    source = tmp_path / "line.geojson"
    write_geojson(
        source,
        {
            "type": "Feature",
            "properties": {"zone_type": "forbidden", "confidence": 0.8},
            "geometry": {"type": "LineString", "coordinates": [[37.0, 55.0], [37.1, 55.1]]},
        },
    )

    with pytest.raises(MODULE.ZoneValidationError, match="Polygon or MultiPolygon"):
        MODULE.normalize_geojson(source, tmp_path / "zones.csv", tmp_path / "report.json")


def test_zone_validator_rejects_slow_zone_without_speed_limit(tmp_path):
    source = tmp_path / "slow-no-speed.geojson"
    write_geojson(
        source,
        {
            "type": "Feature",
            "properties": {"zone_type": "slow", "confidence": 0.8},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[37.0, 55.0], [37.1, 55.0], [37.1, 55.1], [37.0, 55.1], [37.0, 55.0]]],
            },
        },
    )

    with pytest.raises(MODULE.ZoneValidationError, match="zone_speed_limit_kmh is required"):
        MODULE.normalize_geojson(source, tmp_path / "zones.csv", tmp_path / "report.json")


def test_zone_validator_rejects_unsupported_crs(tmp_path):
    source = tmp_path / "wrong-crs.geojson"
    payload = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:3857"}},
        "features": [
            {
                "type": "Feature",
                "properties": {"zone_type": "forbidden", "confidence": 0.8},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[37.0, 55.0], [37.1, 55.0], [37.1, 55.1], [37.0, 55.1], [37.0, 55.0]]],
                },
            }
        ],
    }
    source.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(MODULE.ZoneValidationError, match="EPSG:4326"):
        MODULE.normalize_geojson(source, tmp_path / "zones.csv", tmp_path / "report.json")


def test_import_script_rejects_test_fixture_activation_before_db(tmp_path):
    checksum = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    env = os.environ.copy()
    env.update(
        {
            "MICROMOBILITY_ZONES_FILE": str(FIXTURE),
            "DATASET_VERSION": "test-only-micromobility-zones",
            "SOURCE_NAME": "test-only-fixture",
            "SOURCE_OWNER": "SafeRoute tests",
            "SOURCE_URL": "tests/fixtures/micromobility_zones/test-only-zones.geojson",
            "SOURCE_LICENSE": "test-only",
            "SOURCE_CHECKSUM": f"sha256:{checksum}",
            "ACTIVATE_ENRICHMENT": "true",
            "PSQL_BIN": str(tmp_path / "missing-psql"),
        }
    )

    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "data" / "import-micromobility-zones.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "tests/fixtures cannot be activated" in result.stderr
