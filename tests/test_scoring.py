import pytest

from app.services.routing import scoring_edges_cte_sql
from app.services.scoring import (
    RouteAttributeSummary,
    RoutingMode,
    SCORING_CONFIGS,
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
    sql = combined_filter_sql("walk", "TRUE", "accessible", {"access", "highway", "forbidden_zone"})

    assert "access" in sql
    assert "private" in sql
    assert "forbidden_zone" in sql
    assert "steps" in sql
    assert "motorway" in sql


def test_bike_hard_avoid_uses_explicit_micromobility_forbidden_data():
    sql = combined_filter_sql("bike", "TRUE", "balanced", {"highway", "micromobility_allowed"})

    assert "micromobility_allowed" in sql
    assert "forbidden" in sql
    assert "steps" in sql


def test_attribute_summary_sql_omits_missing_optional_columns():
    sql = route_attribute_summary_sql({"safety_weight", "highway"})

    assert "edge.safety_weight" in sql
    assert "edge.highway" in sql
    assert "edge.width" not in sql
    assert "edge.est_width" not in sql


def test_attribute_summary_sql_reads_present_expanded_factor_columns():
    columns = {
        "safety_weight",
        "highway",
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
        "enrichment_confidence",
        "telemetry_confidence",
    }

    sql = route_attribute_summary_sql(columns)

    for column in columns:
        assert f"edge.{column}" in sql
    for alias in [
        "bad_surface_fraction",
        "sidewalk_missing_fraction",
        "min_sidewalk_width_m",
        "avg_curb_risk",
        "max_curb_density_per_km",
        "crossing_count",
        "controlled_crossing_count",
        "uncontrolled_crossing_count",
        "avg_crossing_risk",
        "poor_lighting_fraction",
        "max_slope_percent",
        "avg_traffic_intensity",
        "avg_pedestrian_density",
        "micromobility_forbidden_fraction",
        "forbidden_zone_fraction",
        "micromobility_slow_zone_fraction",
        "min_zone_speed_limit_kmh",
        "avg_road_exposure_proxy",
        "avg_weather_sensitive_risk",
        "avg_enrichment_confidence",
        "avg_telemetry_confidence",
    ]:
        assert alias in sql


def test_attribute_summary_sql_keeps_unavailable_optional_values_null():
    sql = route_attribute_summary_sql({"surface_type", "surface_quality", "lighting_quality"})

    assert "ELSE NULL END" in sql
    assert "surface_type" in sql
    assert "lighting_quality" in sql


def test_cost_expression_uses_present_expanded_factor_columns():
    columns = {
        "length",
        "safety_weight",
        "highway",
        "surface_type",
        "surface_quality",
        "sidewalk_presence",
        "sidewalk_width_m",
        "curb_risk",
        "curb_frequency",
        "curb_density_per_km",
        "crossing_count",
        "crossing_risk",
        "lighting_quality",
        "slope_percent",
        "traffic_intensity",
        "micromobility_allowed",
        "micromobility_slow_zone",
        "road_exposure_proxy",
        "weather_sensitive_risk",
    }

    sql = cost_expression("walk", "accessible", columns)

    for column in columns:
        assert column in sql


def test_scoring_edges_cte_omits_enrichment_join_when_schema_absent():
    sql, projected_columns = scoring_edges_cte_sql({"id", "highway", "safety_weight"}, set())

    assert "safety_edge_enrichment" not in sql
    assert "edge.safety_weight AS safety_weight" in sql
    assert "surface_type" not in projected_columns


def test_scoring_edges_cte_overlays_active_real_enrichment_columns():
    sql, projected_columns = scoring_edges_cte_sql(
        {"id", "highway", "safety_weight", "surface"},
        {"surface_type", "sidewalk_presence", "confidence"},
    )

    assert "LEFT JOIN LATERAL" in sql
    assert "safety_edge_enrichment" in sql
    assert "safety_enrichment_datasets" in sql
    assert "dataset.is_active = true" in sql
    assert "COALESCE((enrichment.surface_type)::TEXT, (edge.surface)::TEXT) AS surface_type" in sql
    assert "enrichment.sidewalk_presence" in sql
    assert "(enrichment.confidence)::TEXT" in sql
    assert {"surface_type", "sidewalk_presence", "enrichment_confidence"} <= projected_columns
    assert "AS telemetry_confidence" not in sql


@pytest.mark.parametrize("mode", list(RoutingMode))
def test_all_modes_return_bounded_public_score(mode):
    result = calculate_route_score(
        RouteAttributeSummary(
            avg_safety_weight=1.6,
            min_width_m=3.0,
            max_speed_kmh=20,
            max_lanes=1,
            track_fraction=0.0,
            bike_lane_fraction=0.0,
            walk_friendly_fraction=0.4,
        ),
        mode,
        "walk",
    )

    assert result.mode is mode
    assert 0 <= result.safety_index <= 100
    assert result.total == result.safety_index
    assert result.to_public_dict()["mode"] == mode.value


def test_missing_optional_attributes_still_produce_explainable_score():
    result = calculate_route_score(
        RouteAttributeSummary(avg_safety_weight=1.8),
        "balanced",
        "walk",
    )

    public = result.to_public_dict()
    assert result.safety_index == 80
    assert public["factors"]["min_width_m"] is None
    assert public["factors"]["max_speed_kmh"] is None
    assert [reason["code"] for reason in public["reasons"]] == ["safety_weight"]
    assert {"code", "impact", "message", "value", "weight"} <= set(public["reasons"][0])


def test_route_score_clamps_lower_and_upper_bounds():
    unsafe = calculate_route_score(
        RouteAttributeSummary(
            avg_safety_weight=9.0,
            min_width_m=0.8,
            max_speed_kmh=80,
            max_lanes=6,
            track_fraction=0.6,
        ),
        "accessible",
        "walk",
    )
    comfortable = calculate_route_score(
        RouteAttributeSummary(
            avg_safety_weight=1.0,
            min_width_m=4.0,
            max_speed_kmh=10,
            max_lanes=1,
            walk_friendly_fraction=1.0,
        ),
        "safest",
        "walk",
    )

    assert unsafe.safety_index == 0
    assert comfortable.safety_index == 100


@pytest.mark.parametrize(
    ("mode", "expected_weights"),
    [
        (RoutingMode.SAFEST, {"narrow_width": 15, "high_speed_or_lanes": 10, "track_like_edges": 8}),
        (RoutingMode.FASTEST, {"narrow_width": 4, "high_speed_or_lanes": 3, "track_like_edges": 2}),
        (RoutingMode.BALANCED, {"narrow_width": 10, "high_speed_or_lanes": 7, "track_like_edges": 5}),
        (RoutingMode.ACCESSIBLE, {"narrow_width": 24, "high_speed_or_lanes": 9, "track_like_edges": 12}),
    ],
)
def test_high_penalty_reasons_use_mode_specific_weights(mode, expected_weights):
    result = calculate_route_score(
        RouteAttributeSummary(
            avg_safety_weight=1.2,
            min_width_m=1.0,
            max_speed_kmh=70,
            max_lanes=4,
            track_fraction=0.25,
        ),
        mode,
        "walk",
    )

    weights_by_code = {reason.code: reason.weight for reason in result.reasons}
    for code, expected_weight in expected_weights.items():
        assert weights_by_code[code] == expected_weight
    assert weights_by_code["narrow_width"] == SCORING_CONFIGS[mode].narrow_width_score_penalty


def test_expanded_scoring_factors_produce_real_reasons_when_values_exist():
    result = calculate_route_score(
        RouteAttributeSummary(
            avg_safety_weight=1.0,
            bad_surface_fraction=0.4,
            sidewalk_missing_fraction=0.5,
            min_sidewalk_width_m=1.0,
            avg_curb_risk=0.7,
            max_curb_density_per_km=12,
            crossing_count=8,
            avg_crossing_risk=0.7,
            poor_lighting_fraction=0.3,
            max_slope_percent=10,
            avg_traffic_intensity=0.8,
            avg_pedestrian_density=0.9,
            micromobility_forbidden_fraction=0.5,
            forbidden_zone_fraction=0.25,
            micromobility_slow_zone_fraction=0.5,
            avg_road_exposure_proxy=0.8,
            avg_weather_sensitive_risk=0.6,
            avg_enrichment_confidence=0.9,
            avg_telemetry_confidence=0.9,
        ),
        "accessible",
        "bike",
    )

    reason_codes = {reason.code for reason in result.reasons}
    assert {
        "bad_surface",
        "missing_sidewalk",
        "narrow_sidewalk_width",
        "curb_risk",
        "many_crossings",
        "poor_lighting",
        "steep_slope",
        "traffic_intensity",
        "high_pedestrian_density",
        "micromobility_forbidden",
        "forbidden_zone",
        "micromobility_slow_zone",
        "road_exposure_proxy",
        "weather_sensitive_risk",
        "telemetry_confidence",
    } <= reason_codes
    assert result.factors["bad_surface_fraction"] == 0.4
    assert result.factors["min_sidewalk_width_m"] == 1.0


def test_expanded_positive_factors_produce_real_reasons_when_values_exist():
    result = calculate_route_score(
        RouteAttributeSummary(
            avg_safety_weight=1.0,
            smooth_surface_fraction=0.8,
            good_lighting_fraction=0.7,
            avg_traffic_intensity=0.1,
            avg_enrichment_confidence=0.85,
            avg_telemetry_confidence=0.85,
        ),
        "safest",
        "walk",
    )

    reason_codes = {reason.code for reason in result.reasons}
    assert {"smooth_surface", "good_lighting", "low_traffic", "telemetry_confidence"} <= reason_codes
    assert result.safety_index == 100


def test_absent_micromobility_zone_data_produces_no_zone_reasons():
    result = calculate_route_score(
        RouteAttributeSummary(avg_safety_weight=1.0),
        "safest",
        "bike",
    )

    reason_codes = {reason.code for reason in result.reasons}
    assert "micromobility_forbidden" not in reason_codes
    assert "forbidden_zone" not in reason_codes
    assert "micromobility_slow_zone" not in reason_codes
    assert result.factors["micromobility_forbidden_fraction"] is None
    assert result.factors["forbidden_zone_fraction"] is None
    assert result.factors["micromobility_slow_zone_fraction"] is None


def test_low_enrichment_confidence_reduces_factor_impact():
    high_confidence = calculate_route_score(
        RouteAttributeSummary(
            avg_safety_weight=1.0,
            bad_surface_fraction=0.5,
            avg_enrichment_confidence=1.0,
        ),
        "balanced",
        "walk",
    )
    low_confidence = calculate_route_score(
        RouteAttributeSummary(
            avg_safety_weight=1.0,
            bad_surface_fraction=0.5,
            avg_enrichment_confidence=0.2,
        ),
        "balanced",
        "walk",
    )

    high_reason = next(reason for reason in high_confidence.reasons if reason.code == "bad_surface")
    low_reason = next(reason for reason in low_confidence.reasons if reason.code == "bad_surface")

    assert high_reason.weight == SCORING_CONFIGS[RoutingMode.BALANCED].bad_surface_score_penalty
    assert low_reason.weight < high_reason.weight
    assert low_confidence.safety_index > high_confidence.safety_index


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
