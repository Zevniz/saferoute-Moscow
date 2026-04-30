from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.telemetry import SidewalkSample, SidewalkTelemetryBatch
from app.services.telemetry import (
    h3_cell_center,
    h3_cell_polygon,
    h3_latlng_to_cell,
    ingest_sidewalk_samples,
    list_sidewalk_cells,
    parse_bbox,
    sample_quality,
    telemetry_batch_resolution,
    telemetry_schema_statements,
)


def test_sidewalk_sample_requires_timezone():
    with pytest.raises(ValidationError):
        SidewalkSample(
            device_id="scooter-1",
            captured_at=datetime(2026, 4, 20, 12, 0, 0),
            lat=55.7558,
            lon=37.6173,
            speed_mps=3.2,
            source="scooter",
        )


def test_quality_score_penalizes_noise_obstacles_and_gps_accuracy():
    sample = SidewalkSample(
        device_id="robot-1",
        captured_at=datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc),
        lat=55.7558,
        lon=37.6173,
        speed_mps=1.1,
        source="robot",
        surface_score=95,
        vibration_rms=2,
        obstacle_score=0.4,
        gps_accuracy_m=20,
    )

    quality, confidence, obstacle, vibration = sample_quality(sample)

    assert 0 <= quality < 95
    assert confidence == 0.6
    assert obstacle == 0.4
    assert vibration == 2


def test_h3_cell_helpers_return_center_and_polygon():
    cell = h3_latlng_to_cell(55.7558, 37.6173, 9)
    lat, lon = h3_cell_center(cell)
    polygon = h3_cell_polygon(cell)

    assert abs(lat - 55.7558) < 0.1
    assert abs(lon - 37.6173) < 0.1
    assert polygon["type"] == "Polygon"
    assert polygon["coordinates"][0][0] == polygon["coordinates"][0][-1]


def test_parse_bbox_rejects_non_finite_values():
    with pytest.raises(ValueError, match="finite"):
        parse_bbox("37.50,55.68,nan,55.82")


def test_parse_bbox_rejects_out_of_range_coordinates():
    with pytest.raises(ValueError, match="valid longitude/latitude"):
        parse_bbox("181,55.68,182,55.82")


def test_sidewalk_sample_rejects_coordinates_outside_product_bounds():
    with pytest.raises(ValidationError):
        SidewalkSample(
            device_id="robot-1",
            captured_at=datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc),
            lat=57.0,
            lon=37.6173,
            speed_mps=1.1,
            source="robot",
        )


def test_ingest_rejects_batch_above_runtime_limit_before_database(monkeypatch):
    class Settings:
        telemetry_max_batch_size = 1

    def fail_if_called():
        raise AssertionError("database schema should not be touched for oversized batches")

    batch = SidewalkTelemetryBatch(
        samples=[
            {
                "device_id": "robot-1",
                "captured_at": "2026-04-20T12:00:00Z",
                "lat": 55.7558,
                "lon": 37.6173,
                "speed_mps": 1.1,
                "source": "robot",
            },
            {
                "device_id": "robot-2",
                "captured_at": "2026-04-20T12:01:00Z",
                "lat": 55.756,
                "lon": 37.618,
                "speed_mps": 1.0,
                "source": "robot",
            },
        ]
    )
    monkeypatch.setattr("app.services.telemetry.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.telemetry.ensure_telemetry_tables", fail_if_called)

    with pytest.raises(ValueError, match="too many telemetry samples"):
        ingest_sidewalk_samples(batch)


def test_sidewalk_cells_validates_bbox_before_touching_database(monkeypatch):
    def fail_if_called():
        raise AssertionError("database setup should not run for invalid bbox")

    monkeypatch.setattr("app.services.telemetry.ensure_telemetry_tables", fail_if_called)

    with pytest.raises(ValueError, match="bbox values must be numeric"):
        list_sidewalk_cells("bad,55.68,37.75,55.82", resolution=9)


def test_telemetry_batch_resolution_uses_config_default_when_omitted(monkeypatch):
    class Settings:
        telemetry_default_h3_resolution = 10

    batch = SidewalkTelemetryBatch(
        samples=[
            {
                "device_id": "robot-1",
                "captured_at": "2026-04-20T12:00:00Z",
                "lat": 55.7558,
                "lon": 37.6173,
                "speed_mps": 1.1,
                "source": "robot",
            }
        ]
    )
    monkeypatch.setattr("app.services.telemetry.get_settings", lambda: Settings())

    assert telemetry_batch_resolution(batch) == 10


def test_telemetry_batch_resolution_preserves_explicit_request_value(monkeypatch):
    class Settings:
        telemetry_default_h3_resolution = 10

    batch = SidewalkTelemetryBatch(
        samples=[
            {
                "device_id": "robot-1",
                "captured_at": "2026-04-20T12:00:00Z",
                "lat": 55.7558,
                "lon": 37.6173,
                "speed_mps": 1.1,
                "source": "robot",
            }
        ],
        h3_resolution=8,
    )
    monkeypatch.setattr("app.services.telemetry.get_settings", lambda: Settings())

    assert telemetry_batch_resolution(batch) == 8


def test_telemetry_schema_statements_include_tables_and_indexes():
    statements = telemetry_schema_statements()
    schema_sql = "\n".join(statements)

    assert "CREATE TABLE IF NOT EXISTS sidewalk_samples" in schema_sql
    assert "CREATE TABLE IF NOT EXISTS sidewalk_cell_aggregates" in schema_sql
    assert "CREATE INDEX IF NOT EXISTS sidewalk_samples_h3_idx" in schema_sql
