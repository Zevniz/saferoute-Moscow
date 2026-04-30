from datetime import datetime, timedelta, timezone

from app.services.scoring import RouteAttributeSummary, calculate_route_score
from app.services.telemetry_confidence import calculate_telemetry_confidence, route_h3_cells


def test_route_h3_cells_samples_linestring_geometry():
    cells = route_h3_cells(
        {"type": "LineString", "coordinates": [[37.6173, 55.7558], [37.6203, 55.7588]]},
        resolution=9,
    )

    assert cells
    assert len(cells) == len(set(cells))


def test_zero_telemetry_rows_return_no_confidence():
    assert calculate_telemetry_confidence(["cell-a", "cell-b"], [], {}, now=datetime(2026, 4, 28, tzinfo=timezone.utc)) is None


def test_real_aggregate_rows_produce_confidence_metadata():
    now = datetime(2026, 4, 28, 12, tzinfo=timezone.utc)
    result = calculate_telemetry_confidence(
        ["cell-a", "cell-b"],
        [
            {"h3_cell": "cell-a", "sample_count": 30, "confidence_sum": 28.5, "last_seen_at": now - timedelta(hours=2)},
            {"h3_cell": "cell-b", "sample_count": 25, "confidence_sum": 23.0, "last_seen_at": now - timedelta(hours=3)},
        ],
        {
            "cell-a": {"raw_count": 30, "quality_stddev": 2.0},
            "cell-b": {"raw_count": 25, "quality_stddev": 3.0},
        },
        now=now,
    )

    assert result is not None
    assert result.confidence >= 0.75
    assert result.source["active"] is True
    assert result.source["sample_count"] == 55
    assert result.source["cell_count"] == 2
    assert result.source["coverage_fraction"] == 1.0
    assert result.source["avg_confidence"] == result.confidence


def test_stale_observations_reduce_telemetry_confidence():
    now = datetime(2026, 4, 28, 12, tzinfo=timezone.utc)
    recent = calculate_telemetry_confidence(
        ["cell-a"],
        [{"h3_cell": "cell-a", "sample_count": 30, "confidence_sum": 28.5, "last_seen_at": now - timedelta(hours=2)}],
        {"cell-a": {"raw_count": 30, "quality_stddev": 2.0}},
        now=now,
    )
    stale = calculate_telemetry_confidence(
        ["cell-a"],
        [{"h3_cell": "cell-a", "sample_count": 30, "confidence_sum": 28.5, "last_seen_at": now - timedelta(days=90)}],
        {"cell-a": {"raw_count": 30, "quality_stddev": 2.0}},
        now=now,
    )

    assert recent is not None and stale is not None
    assert stale.confidence < recent.confidence


def test_low_sample_count_reduces_telemetry_confidence():
    now = datetime(2026, 4, 28, 12, tzinfo=timezone.utc)
    strong = calculate_telemetry_confidence(
        ["cell-a"],
        [{"h3_cell": "cell-a", "sample_count": 30, "confidence_sum": 28.5, "last_seen_at": now}],
        {"cell-a": {"raw_count": 30, "quality_stddev": 2.0}},
        now=now,
    )
    sparse = calculate_telemetry_confidence(
        ["cell-a"],
        [{"h3_cell": "cell-a", "sample_count": 1, "confidence_sum": 0.95, "last_seen_at": now}],
        {"cell-a": {"raw_count": 1, "quality_stddev": 0.0}},
        now=now,
    )

    assert strong is not None and sparse is not None
    assert sparse.confidence < strong.confidence


def test_inconsistent_raw_samples_reduce_agreement_score():
    now = datetime(2026, 4, 28, 12, tzinfo=timezone.utc)
    consistent = calculate_telemetry_confidence(
        ["cell-a"],
        [{"h3_cell": "cell-a", "sample_count": 30, "confidence_sum": 28.5, "last_seen_at": now}],
        {"cell-a": {"raw_count": 30, "quality_stddev": 2.0}},
        now=now,
    )
    noisy = calculate_telemetry_confidence(
        ["cell-a"],
        [{"h3_cell": "cell-a", "sample_count": 30, "confidence_sum": 28.5, "last_seen_at": now}],
        {"cell-a": {"raw_count": 30, "quality_stddev": 45.0}},
        now=now,
    )

    assert consistent is not None and noisy is not None
    assert noisy.confidence < consistent.confidence
    assert noisy.source["component_scores"]["agreement_score"] < consistent.source["component_scores"]["agreement_score"]


def test_telemetry_confidence_reason_requires_real_computed_factor():
    absent = calculate_route_score(RouteAttributeSummary(avg_safety_weight=1.0), "safest", "walk")
    present = calculate_route_score(
        RouteAttributeSummary(avg_safety_weight=1.0, avg_telemetry_confidence=0.9),
        "safest",
        "walk",
    )

    assert "telemetry_confidence" not in {reason.code for reason in absent.reasons}
    assert "telemetry_confidence" in {reason.code for reason in present.reasons}
