import pytest

from app.services.scoring import (
    RouteAttributeSummary,
    RoutingMode,
    calculate_route_score,
    combined_filter_sql,
    cost_expression,
    normalize_route_mode,
    route_attribute_summary_sql,
)


def test_route_mode_enum_normalizes_valid_modes():
    assert normalize_route_mode("safest") is RoutingMode.SAFEST
    assert normalize_route_mode(RoutingMode.ACCESSIBLE) is RoutingMode.ACCESSIBLE


def test_route_mode_enum_rejects_unknown_modes():
    with pytest.raises(ValueError, match="route mode"):
        normalize_route_mode("shortest")


def test_cost_expression_uses_only_available_columns():
    sql = cost_expression("walk", "safest", {"length", "safety_weight", "highway"})

    assert "safety_weight" in sql
    assert "highway" in sql
    assert "width" not in sql
    assert "est_width" not in sql


def test_combined_filter_hard_avoids_real_forbidden_attributes():
    sql = combined_filter_sql("walk", "TRUE", "accessible", {"access", "highway"})

    assert "access" in sql
    assert "private" in sql
    assert "steps" in sql
    assert "motorway" in sql


def test_attribute_summary_sql_omits_missing_optional_columns():
    sql = route_attribute_summary_sql({"safety_weight", "highway"})

    assert "edge.safety_weight" in sql
    assert "edge.highway" in sql
    assert "edge.width" not in sql
    assert "edge.est_width" not in sql


def test_accessible_scoring_penalizes_narrow_track_like_routes():
    result = calculate_route_score(
        RouteAttributeSummary(
            avg_safety_weight=1.4,
            min_width_m=1.0,
            max_speed_kmh=20,
            max_lanes=1,
            track_fraction=0.4,
            bike_lane_fraction=0.0,
            walk_friendly_fraction=0.1,
        ),
        "accessible",
        "walk",
    )

    assert result.mode is RoutingMode.ACCESSIBLE
    assert result.safety_index < 90
    reason_codes = {reason.code for reason in result.reasons}
    assert "narrow_width" in reason_codes
    assert "track_like_edges" in reason_codes


def test_bike_scoring_explains_cycleway_bonus():
    result = calculate_route_score(
        RouteAttributeSummary(
            avg_safety_weight=1.0,
            min_width_m=3.2,
            max_speed_kmh=20,
            max_lanes=1,
            track_fraction=0.0,
            bike_lane_fraction=0.6,
            walk_friendly_fraction=0.0,
        ),
        "safest",
        "bike",
    )

    assert result.safety_index == 100
    reason_codes = {reason.code for reason in result.reasons}
    assert "cycleway_edges" in reason_codes
    assert result.to_public_dict()["reasons"]
