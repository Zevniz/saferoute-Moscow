import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "data" / "validate-measured-layer-csv.py"
TRAFFIC_IMPORT = ROOT / "scripts" / "data" / "import-measured-traffic.sh"
PEDESTRIAN_IMPORT = ROOT / "scripts" / "data" / "import-pedestrian-density.sh"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def run_script(path: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    merged_env.update(env)
    return subprocess.run(
        ["bash", str(path)],
        cwd=ROOT,
        env=merged_env,
        capture_output=True,
        text=True,
    )


def test_measured_traffic_validator_normalizes_real_measured_rows(tmp_path):
    source = ROOT / "tests" / "fixtures" / "measured_layers" / "test-only-measured-traffic.csv"
    normalized = tmp_path / "normalized.csv"
    report = tmp_path / "report.json"

    result = subprocess.run(
        [sys.executable, str(VALIDATOR), "measured_traffic", str(source), str(normalized), str(report)],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {"status": "ok", "row_count": 1, "active_factor": "traffic_intensity"}
    normalized_lines = normalized.read_text(encoding="utf-8").splitlines()
    assert normalized_lines[0].startswith("edge_id,confidence,observed_at")
    assert ",0.73," in normalized_lines[1]
    report_payload = json.loads(report.read_text(encoding="utf-8"))
    assert report_payload["factor_counts"] == {"traffic_intensity": 1}


def test_pedestrian_density_validator_normalizes_real_measured_rows(tmp_path):
    source = ROOT / "tests" / "fixtures" / "measured_layers" / "test-only-pedestrian-density.csv"
    normalized = tmp_path / "normalized.csv"
    report = tmp_path / "report.json"

    result = subprocess.run(
        [sys.executable, str(VALIDATOR), "pedestrian_density", str(source), str(normalized), str(report)],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {"status": "ok", "row_count": 1, "active_factor": "pedestrian_density"}
    normalized_row = normalized.read_text(encoding="utf-8").splitlines()[1]
    assert ",0.62," in normalized_row
    report_payload = json.loads(report.read_text(encoding="utf-8"))
    assert report_payload["factor_counts"] == {"pedestrian_density": 1}


def test_measured_traffic_validator_rejects_osm_road_class_proxy(tmp_path):
    source = tmp_path / "osm-proxy-traffic.csv"
    normalized = tmp_path / "normalized.csv"
    report = tmp_path / "report.json"
    source.write_text(
        "edge_id,confidence,observed_at,traffic_intensity,traffic_volume,source_category\n"
        "42,0.7,2026-04-28T10:00:00Z,0.8,1000,osm_maxspeed_lanes\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(VALIDATOR), "measured_traffic", str(source), str(normalized), str(report)],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "measured traffic cannot be activated from proxy/source tokens" in result.stderr


def test_measured_traffic_validator_rejects_missing_measured_raw_field(tmp_path):
    source = tmp_path / "no-raw-traffic.csv"
    normalized = tmp_path / "normalized.csv"
    report = tmp_path / "report.json"
    source.write_text(
        "edge_id,confidence,observed_at,traffic_intensity,source_category\n"
        "42,0.7,2026-04-28T10:00:00Z,0.8,measured_sensor_export\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(VALIDATOR), "measured_traffic", str(source), str(normalized), str(report)],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "requires at least one measured raw field" in result.stderr


def test_pedestrian_density_validator_rejects_poi_transit_proxy(tmp_path):
    source = tmp_path / "poi-proxy-pedestrian.csv"
    normalized = tmp_path / "normalized.csv"
    report = tmp_path / "report.json"
    source.write_text(
        "edge_id,confidence,observed_at,pedestrian_density,pedestrian_count,source_category\n"
        "42,0.7,2026-04-28T10:00:00Z,0.8,120,poi_transit_proxy\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(VALIDATOR), "pedestrian_density", str(source), str(normalized), str(report)],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "pedestrian density cannot be activated from proxy/source tokens" in result.stderr


def test_measured_traffic_import_rejects_missing_provenance(tmp_path):
    source = tmp_path / "traffic.csv"
    source.write_text(
        "edge_id,confidence,observed_at,traffic_intensity,traffic_volume,source_category\n"
        "42,0.82,2026-04-28T10:00:00Z,0.73,1840,measured_sensor_export\n",
        encoding="utf-8",
    )

    result = run_script(
        TRAFFIC_IMPORT,
        {
            "MEASURED_TRAFFIC_FILE": str(source),
            "DATASET_VERSION": "test-only-measured-traffic",
            "SOURCE_NAME": "test-only",
        },
    )

    assert result.returncode != 0
    assert "SOURCE_OWNER is required" in result.stderr


def test_measured_traffic_import_rejects_commercial_activation_without_license_confirmation(tmp_path):
    source = tmp_path / "licensed-export-required.csv"
    source.write_text(
        "edge_id,confidence,observed_at,traffic_intensity,traffic_volume,source_category\n"
        "42,0.82,2026-04-28T10:00:00Z,0.73,1840,measured_sensor_export\n",
        encoding="utf-8",
    )

    result = run_script(
        TRAFFIC_IMPORT,
        {
            "MEASURED_TRAFFIC_FILE": str(source),
            "DATASET_VERSION": "xmap-test-only",
            "SOURCE_NAME": "xMap Russia Road Traffic Data",
            "SOURCE_OWNER": "xMap",
            "SOURCE_URL": "https://www.xmap.ai/data-catalogs/russia-road-traffic-data",
            "SOURCE_LICENSE": "commercial contract required",
            "SOURCE_CHECKSUM": sha256(source),
            "EDGE_MAPPING_METHOD": "provider_edge_id_to_public_moscow_network_id",
            "ACTIVATE_ENRICHMENT": "true",
            "SOURCE_LICENSE_CONFIRMED": "false",
        },
    )

    assert result.returncode != 0
    assert "SOURCE_LICENSE_CONFIRMED=true" in result.stderr


def test_measured_traffic_import_rejects_test_fixture_activation():
    source = ROOT / "tests" / "fixtures" / "measured_layers" / "test-only-measured-traffic.csv"

    result = run_script(
        TRAFFIC_IMPORT,
        {
            "MEASURED_TRAFFIC_FILE": str(source),
            "DATASET_VERSION": "test-only-measured-traffic",
            "SOURCE_NAME": "test-only measured traffic",
            "SOURCE_OWNER": "tests",
            "SOURCE_URL": "local:test-fixture",
            "SOURCE_LICENSE": "test-only",
            "SOURCE_CHECKSUM": sha256(source),
            "EDGE_MAPPING_METHOD": "test_fixture_edge_id",
            "ACTIVATE_ENRICHMENT": "true",
            "SOURCE_LICENSE_CONFIRMED": "true",
        },
    )

    assert result.returncode != 0
    assert "tests/fixtures cannot be activated" in result.stderr

def test_pedestrian_density_import_rejects_test_fixture_activation():
    source = ROOT / "tests" / "fixtures" / "measured_layers" / "test-only-pedestrian-density.csv"

    result = run_script(
        PEDESTRIAN_IMPORT,
        {
            "PEDESTRIAN_DENSITY_FILE": str(source),
            "DATASET_VERSION": "test-only-pedestrian-density",
            "SOURCE_NAME": "test-only pedestrian density",
            "SOURCE_OWNER": "tests",
            "SOURCE_URL": "local:test-fixture",
            "SOURCE_LICENSE": "test-only",
            "SOURCE_CHECKSUM": sha256(source),
            "EDGE_MAPPING_METHOD": "test_fixture_edge_id",
            "ACTIVATE_ENRICHMENT": "true",
            "SOURCE_LICENSE_CONFIRMED": "true",
        },
    )

    assert result.returncode != 0
    assert "tests/fixtures cannot be activated" in result.stderr
