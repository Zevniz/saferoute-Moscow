"""Mode-aware SafeRoute scoring primitives.

This module intentionally uses only attributes that are present in the current
`public.moscow_network` graph. Future factors such as lighting, slope, surface
quality, curb density, and sidewalk presence are read only when real graph
columns or overlays exist; missing factors are not inferred.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

ScoreImpact = Literal["positive", "penalty", "neutral"]


class RoutingMode(str, Enum):
    """Supported user-facing route scoring modes."""

    SAFEST = "safest"
    FASTEST = "fastest"
    BALANCED = "balanced"
    ACCESSIBLE = "accessible"


@dataclass(frozen=True)
class ScoringConfig:
    """Weights for graph cost and route-score explanation."""

    safety_weight_factor: float
    traffic_cost_penalty: float
    narrow_width_cost_penalty: float
    narrow_width_score_penalty: int
    medium_width_score_penalty: int
    traffic_score_penalty: int
    track_score_penalty: int
    bike_lane_score_bonus: int
    walk_friendly_score_bonus: int
    low_speed_score_bonus: int
    bad_surface_score_penalty: int
    smooth_surface_score_bonus: int
    missing_sidewalk_score_penalty: int
    curb_risk_score_penalty: int
    crossing_score_penalty: int
    poor_lighting_score_penalty: int
    good_lighting_score_bonus: int
    slope_score_penalty: int
    traffic_intensity_score_penalty: int
    low_traffic_score_bonus: int
    pedestrian_density_score_penalty: int
    micromobility_forbidden_score_penalty: int
    weather_sensitive_score_penalty: int
    telemetry_confidence_score_bonus: int

    @property
    def medium_width_cost_penalty(self) -> float:
        """Moderate width penalty derived from the mode's narrow penalty."""

        return max(1.05, round((self.narrow_width_cost_penalty + 1.0) / 2.0, 3))


SCORING_CONFIGS: dict[RoutingMode, ScoringConfig] = {
    RoutingMode.SAFEST: ScoringConfig(
        safety_weight_factor=1.2,
        traffic_cost_penalty=1.5,
        narrow_width_cost_penalty=2.4,
        narrow_width_score_penalty=15,
        medium_width_score_penalty=7,
        traffic_score_penalty=10,
        track_score_penalty=8,
        bike_lane_score_bonus=5,
        walk_friendly_score_bonus=5,
        low_speed_score_bonus=3,
        bad_surface_score_penalty=12,
        smooth_surface_score_bonus=4,
        missing_sidewalk_score_penalty=18,
        curb_risk_score_penalty=10,
        crossing_score_penalty=7,
        poor_lighting_score_penalty=7,
        good_lighting_score_bonus=3,
        slope_score_penalty=8,
        traffic_intensity_score_penalty=8,
        low_traffic_score_bonus=3,
        pedestrian_density_score_penalty=4,
        micromobility_forbidden_score_penalty=20,
        weather_sensitive_score_penalty=6,
        telemetry_confidence_score_bonus=3,
    ),
    RoutingMode.BALANCED: ScoringConfig(
        safety_weight_factor=0.75,
        traffic_cost_penalty=1.25,
        narrow_width_cost_penalty=1.7,
        narrow_width_score_penalty=10,
        medium_width_score_penalty=5,
        traffic_score_penalty=7,
        track_score_penalty=5,
        bike_lane_score_bonus=4,
        walk_friendly_score_bonus=4,
        low_speed_score_bonus=2,
        bad_surface_score_penalty=8,
        smooth_surface_score_bonus=3,
        missing_sidewalk_score_penalty=12,
        curb_risk_score_penalty=7,
        crossing_score_penalty=5,
        poor_lighting_score_penalty=5,
        good_lighting_score_bonus=2,
        slope_score_penalty=5,
        traffic_intensity_score_penalty=6,
        low_traffic_score_bonus=2,
        pedestrian_density_score_penalty=3,
        micromobility_forbidden_score_penalty=16,
        weather_sensitive_score_penalty=4,
        telemetry_confidence_score_bonus=2,
    ),
    RoutingMode.FASTEST: ScoringConfig(
        safety_weight_factor=0.25,
        traffic_cost_penalty=1.08,
        narrow_width_cost_penalty=1.15,
        narrow_width_score_penalty=4,
        medium_width_score_penalty=2,
        traffic_score_penalty=3,
        track_score_penalty=2,
        bike_lane_score_bonus=2,
        walk_friendly_score_bonus=2,
        low_speed_score_bonus=1,
        bad_surface_score_penalty=3,
        smooth_surface_score_bonus=1,
        missing_sidewalk_score_penalty=5,
        curb_risk_score_penalty=3,
        crossing_score_penalty=2,
        poor_lighting_score_penalty=2,
        good_lighting_score_bonus=1,
        slope_score_penalty=2,
        traffic_intensity_score_penalty=3,
        low_traffic_score_bonus=1,
        pedestrian_density_score_penalty=1,
        micromobility_forbidden_score_penalty=12,
        weather_sensitive_score_penalty=2,
        telemetry_confidence_score_bonus=1,
    ),
    RoutingMode.ACCESSIBLE: ScoringConfig(
        safety_weight_factor=1.35,
        traffic_cost_penalty=1.45,
        narrow_width_cost_penalty=5.0,
        narrow_width_score_penalty=24,
        medium_width_score_penalty=12,
        traffic_score_penalty=9,
        track_score_penalty=12,
        bike_lane_score_bonus=3,
        walk_friendly_score_bonus=6,
        low_speed_score_bonus=3,
        bad_surface_score_penalty=16,
        smooth_surface_score_bonus=3,
        missing_sidewalk_score_penalty=28,
        curb_risk_score_penalty=18,
        crossing_score_penalty=10,
        poor_lighting_score_penalty=6,
        good_lighting_score_bonus=2,
        slope_score_penalty=16,
        traffic_intensity_score_penalty=7,
        low_traffic_score_bonus=2,
        pedestrian_density_score_penalty=5,
        micromobility_forbidden_score_penalty=24,
        weather_sensitive_score_penalty=8,
        telemetry_confidence_score_bonus=2,
    ),
}


@dataclass(frozen=True)
class RouteAttributeSummary:
    """Aggregated real graph attributes sampled along one route geometry."""

    avg_safety_weight: float | None = None
    min_width_m: float | None = None
    max_speed_kmh: float | None = None
    max_lanes: float | None = None
    track_fraction: float = 0.0
    bike_lane_fraction: float = 0.0
    walk_friendly_fraction: float = 0.0
    bad_surface_fraction: float | None = None
    smooth_surface_fraction: float | None = None
    broken_surface_fraction: float | None = None
    sidewalk_missing_fraction: float | None = None
    min_sidewalk_width_m: float | None = None
    avg_curb_risk: float | None = None
    max_curb_frequency: float | None = None
    max_curb_density_per_km: float | None = None
    crossing_count: float | None = None
    controlled_crossing_count: float | None = None
    uncontrolled_crossing_count: float | None = None
    avg_crossing_risk: float | None = None
    poor_lighting_fraction: float | None = None
    good_lighting_fraction: float | None = None
    max_slope_percent: float | None = None
    avg_traffic_intensity: float | None = None
    avg_pedestrian_density: float | None = None
    micromobility_forbidden_fraction: float | None = None
    forbidden_zone_fraction: float | None = None
    micromobility_slow_zone_fraction: float | None = None
    min_zone_speed_limit_kmh: float | None = None
    avg_road_exposure_proxy: float | None = None
    avg_weather_sensitive_risk: float | None = None
    weather_confidence: float | None = None
    avg_enrichment_confidence: float | None = None
    avg_telemetry_confidence: float | None = None


@dataclass(frozen=True)
class ScoreReason:
    """One machine-readable explanation for a score adjustment."""

    code: str
    impact: ScoreImpact
    message: str
    value: float
    weight: float

    def to_public_dict(self) -> dict[str, str | float]:
        """Return an API-safe explanation shape."""

        return {
            "code": self.code,
            "impact": self.impact,
            "message": self.message,
            "value": round(self.value, 3),
            "weight": round(self.weight, 3),
        }


@dataclass(frozen=True)
class RouteScoreResult:
    """Final route score plus explainability details."""

    mode: RoutingMode
    total: int
    safety_index: int
    reasons: tuple[ScoreReason, ...]
    factors: dict[str, float | None]
    data_sources: dict[str, object] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, object]:
        """Return a backward-compatible additive API payload."""

        return {
            "mode": self.mode.value,
            "total": self.total,
            "safety_index": self.safety_index,
            "factors": self.factors,
            "reasons": [reason.to_public_dict() for reason in self.reasons],
            "data_sources": self.data_sources,
        }


def normalize_route_mode(mode: str | RoutingMode) -> RoutingMode:
    """Return a supported route mode or fail closed for internal callers."""

    if isinstance(mode, RoutingMode):
        return mode
    normalized = mode.lower()
    try:
        return RoutingMode(normalized)
    except ValueError as exc:
        raise ValueError("route mode must be one of: accessible, balanced, fastest, safest") from exc


def clamp_score(value: float) -> int:
    """Clamp a score to SafeRoute's public 0..100 safety scale."""

    return round(max(0.0, min(100.0, value)))


def calculate_safety_index(avg_weight: float | None) -> int:
    """Convert average safety weight into a 0-100 safety index."""

    weight = avg_weight or 1.0
    safety = 100 - (((weight - 1.0) / 4.0) * 100.0)
    return clamp_score(safety)


def enrichment_confidence_multiplier(summary: RouteAttributeSummary) -> float:
    """Scale enrichment impact down when a real dataset reports low confidence."""

    if summary.avg_enrichment_confidence is None:
        return 1.0
    return max(0.25, min(1.0, summary.avg_enrichment_confidence))


def confidence_weight(base_weight: float, multiplier: float) -> float:
    """Return an explainable weighted score adjustment."""

    return round(base_weight * multiplier, 3)


def _qualified_column(column: str, table_alias: str | None) -> str:
    if table_alias:
        return f"{table_alias}.{column}"
    return column


def first_available_column(columns: tuple[str, ...], available_columns: set[str]) -> str | None:
    """Return the first canonical column that exists in the graph."""

    return next((column for column in columns if column in available_columns), None)


def lower_text_column(column: str, available_columns: set[str], table_alias: str | None = None) -> str:
    """Return a lowercase SQL expression for an optional text graph column."""

    if column in available_columns:
        qualified = _qualified_column(column, table_alias)
        return f"LOWER(COALESCE(({qualified})::TEXT, ''))"
    return "''"


def lower_first_text_column(columns: tuple[str, ...], available_columns: set[str], table_alias: str | None = None) -> str:
    """Return a lowercase SQL expression for the first available text column."""

    column = first_available_column(columns, available_columns)
    if column is None:
        return "''"
    return lower_text_column(column, available_columns, table_alias)


def numeric_text_column(column: str, available_columns: set[str], table_alias: str | None = None) -> str:
    """Return a numeric SQL expression for optional text numeric graph columns."""

    if column not in available_columns:
        return "NULL::DOUBLE PRECISION"
    qualified = _qualified_column(column, table_alias)
    return f"""
        CASE
            WHEN ({qualified})::TEXT ~ '^-?[0-9]+(\\.[0-9]+)?$' THEN ({qualified})::DOUBLE PRECISION
            ELSE NULL::DOUBLE PRECISION
        END
    """


def numeric_first_text_column(columns: tuple[str, ...], available_columns: set[str], table_alias: str | None = None) -> str:
    """Return a numeric SQL expression for the first available numeric/text column."""

    column = first_available_column(columns, available_columns)
    if column is None:
        return "NULL::DOUBLE PRECISION"
    return numeric_text_column(column, available_columns, table_alias)


def optional_average_sql(expression: str, alias: str, enabled: bool) -> str:
    """Return AVG(expression) or a typed NULL for missing optional factors."""

    if not enabled:
        return f"NULL::DOUBLE PRECISION AS {alias}"
    return f"AVG({expression}) AS {alias}"


def optional_max_sql(expression: str, alias: str, enabled: bool) -> str:
    """Return MAX(expression) or a typed NULL for missing optional factors."""

    if not enabled:
        return f"NULL::DOUBLE PRECISION AS {alias}"
    return f"MAX({expression}) AS {alias}"


def optional_min_sql(expression: str, alias: str, enabled: bool) -> str:
    """Return MIN(expression) or a typed NULL for missing optional factors."""

    if not enabled:
        return f"NULL::DOUBLE PRECISION AS {alias}"
    return f"MIN({expression}) AS {alias}"


def optional_sum_sql(expression: str, alias: str, enabled: bool) -> str:
    """Return SUM(expression) or a typed NULL for missing optional factors."""

    if not enabled:
        return f"NULL::DOUBLE PRECISION AS {alias}"
    return f"SUM({expression}) AS {alias}"


def explicit_false_sql(expression: str) -> str:
    """SQL predicate for explicit false/no values without treating blanks as false."""

    return f"{expression} IN ('no', 'false', '0', 'none', 'absent', 'missing', 'forbidden')"


def explicit_true_sql(expression: str) -> str:
    """SQL predicate for explicit true/yes values without treating blanks as true."""

    return f"{expression} IN ('yes', 'true', '1', 'present', 'both', 'left', 'right', 'allowed')"


def route_comfort_multiplier_sql(profile: str, mode: str | RoutingMode, available_columns: set[str]) -> str:
    """Build a real-data safety multiplier from available graph attributes."""

    routing_mode = normalize_route_mode(mode)
    config = SCORING_CONFIGS[routing_mode]
    highway = lower_text_column("highway", available_columns)
    surface_type = lower_first_text_column(("surface_type", "surface"), available_columns)
    surface_quality = lower_text_column("surface_quality", available_columns)
    sidewalk_presence = lower_text_column("sidewalk_presence", available_columns)
    sidewalk_width = numeric_first_text_column(("sidewalk_width_m", "sidewalk_width"), available_columns)
    curb_risk = numeric_text_column("curb_risk", available_columns)
    curb_frequency = numeric_text_column("curb_frequency", available_columns)
    curb_density_per_km = numeric_text_column("curb_density_per_km", available_columns)
    crossing_count = numeric_text_column("crossing_count", available_columns)
    crossing_risk = numeric_text_column("crossing_risk", available_columns)
    lighting_quality = lower_text_column("lighting_quality", available_columns)
    slope_percent = numeric_first_text_column(("slope_percent", "incline"), available_columns)
    traffic_intensity = numeric_text_column("traffic_intensity", available_columns)
    micromobility_allowed = lower_text_column("micromobility_allowed", available_columns)
    micromobility_slow_zone = lower_text_column("micromobility_slow_zone", available_columns)
    road_exposure_proxy = numeric_text_column("road_exposure_proxy", available_columns)
    weather_sensitive_risk = numeric_text_column("weather_sensitive_risk", available_columns)
    maxspeed = numeric_text_column("maxspeed", available_columns)
    lanes = numeric_text_column("lanes", available_columns)
    width = f"COALESCE({numeric_text_column('est_width', available_columns)}, {numeric_text_column('width', available_columns)})"
    safety_weight = "COALESCE(safety_weight, 1.0)" if "safety_weight" in available_columns else "1.0"
    safety_factor = f"(1.0 + GREATEST({safety_weight} - 1.0, 0.0) * {config.safety_weight_factor})"

    bike_lane_bonus = "0.72" if profile == "bike" else "1.0"
    walk_path_bonus = "0.86" if profile == "walk" else "1.0"

    return f"""
        (
            {safety_factor}
            * CASE
                WHEN {surface_type} IN ('cobblestone', 'gravel', 'dirt') OR {surface_quality} = 'broken'
                THEN {1.0 + config.bad_surface_score_penalty / 20.0}
                WHEN {surface_type} = 'asphalt' OR {surface_quality} = 'smooth'
                THEN 0.92
                ELSE 1.0
              END
            * CASE
                WHEN {explicit_false_sql(sidewalk_presence)} THEN {1.0 + config.missing_sidewalk_score_penalty / 25.0}
                WHEN {sidewalk_width} IS NOT NULL AND {sidewalk_width} < 1.2 THEN {config.narrow_width_cost_penalty}
                WHEN {sidewalk_width} IS NOT NULL AND {sidewalk_width} < 1.8 THEN {config.medium_width_cost_penalty}
                ELSE 1.0
              END
            * CASE
                WHEN {curb_risk} IS NOT NULL AND {curb_risk} >= 0.6 THEN {1.0 + config.curb_risk_score_penalty / 20.0}
                WHEN {curb_frequency} IS NOT NULL AND {curb_frequency} >= 5 THEN {1.0 + config.curb_risk_score_penalty / 20.0}
                WHEN {curb_density_per_km} IS NOT NULL AND {curb_density_per_km} >= 10 THEN {1.0 + config.curb_risk_score_penalty / 20.0}
                ELSE 1.0
              END
            * CASE
                WHEN {crossing_count} IS NOT NULL AND {crossing_count} >= 6 THEN {1.0 + config.crossing_score_penalty / 25.0}
                WHEN {crossing_risk} IS NOT NULL AND {crossing_risk} >= 0.5 THEN {1.0 + config.crossing_score_penalty / 25.0}
                ELSE 1.0
              END
            * CASE
                WHEN {lighting_quality} IN ('poor', 'bad', 'unlit') THEN {1.0 + config.poor_lighting_score_penalty / 25.0}
                WHEN {lighting_quality} IN ('good', 'well_lit') THEN 0.95
                ELSE 1.0
              END
            * CASE
                WHEN {slope_percent} IS NOT NULL AND ABS({slope_percent}) >= 8 THEN {1.0 + config.slope_score_penalty / 20.0}
                ELSE 1.0
              END
            * CASE
                WHEN {traffic_intensity} IS NOT NULL AND {traffic_intensity} >= 0.7 THEN {1.0 + config.traffic_intensity_score_penalty / 20.0}
                WHEN {traffic_intensity} IS NOT NULL AND {traffic_intensity} <= 0.25 THEN 0.95
                ELSE 1.0
              END
            * CASE
                WHEN {micromobility_allowed} IN ('no', 'false', '0', 'forbidden') THEN {1.0 + config.micromobility_forbidden_score_penalty / 25.0}
                WHEN {explicit_true_sql(micromobility_slow_zone)} THEN {1.0 + config.micromobility_forbidden_score_penalty / 40.0}
                ELSE 1.0
              END
            * CASE
                WHEN {weather_sensitive_risk} IS NOT NULL AND {weather_sensitive_risk} >= 0.5 THEN {1.0 + config.weather_sensitive_score_penalty / 25.0}
                ELSE 1.0
              END
            * CASE
                WHEN {width} IS NOT NULL AND {width} < 1.2 THEN {config.narrow_width_cost_penalty}
                WHEN {width} IS NOT NULL AND {width} < 1.8 THEN {config.medium_width_cost_penalty}
                WHEN {width} IS NOT NULL AND {width} >= 3.0 THEN 0.86
                ELSE 1.0
              END
            * CASE
                WHEN {maxspeed} IS NOT NULL AND {maxspeed} >= 60 THEN {config.traffic_cost_penalty}
                WHEN {lanes} IS NOT NULL AND {lanes} >= 4 THEN {config.traffic_cost_penalty}
                WHEN {road_exposure_proxy} IS NOT NULL AND {road_exposure_proxy} >= 0.75 THEN {config.traffic_cost_penalty}
                WHEN {maxspeed} IS NOT NULL AND {maxspeed} <= 20 THEN 0.92
                ELSE 1.0
              END
            * CASE
                WHEN {highway} LIKE '%%cycleway%%' THEN {bike_lane_bonus}
                WHEN {highway} LIKE '%%footway%%' OR {highway} LIKE '%%pedestrian%%' THEN {walk_path_bonus}
                WHEN {highway} LIKE '%%track%%' THEN 1.35
                ELSE 1.0
              END
        )
    """


def cost_expression(profile: str, mode: str | RoutingMode, available_columns: set[str]) -> str:
    """Build a mode-aware graph cost using only real available columns."""

    return f"(COALESCE(length, 0.0) * {route_comfort_multiplier_sql(profile, mode, available_columns)})"


def forbidden_access_filter_sql(available_columns: set[str]) -> str:
    """Reject graph edges with explicit forbidden access when data exists."""

    if "access" not in available_columns:
        return "TRUE"
    access = lower_text_column("access", available_columns)
    return f"({access} = '' OR {access} NOT IN ('no', 'private', 'restricted'))"


def hard_avoid_filter_sql(profile: str, mode: str | RoutingMode, available_columns: set[str]) -> str:
    """Build hard-avoid filters for real forbidden and unsuitable graph edges."""

    routing_mode = normalize_route_mode(mode)
    highway = lower_text_column("highway", available_columns)
    forbidden_zone = lower_text_column("forbidden_zone", available_columns)
    micromobility_allowed = lower_text_column("micromobility_allowed", available_columns)
    filters = [forbidden_access_filter_sql(available_columns)]
    if "forbidden_zone" in available_columns:
        filters.append(f"NOT ({explicit_true_sql(forbidden_zone)})")
    if profile == "bike" and "micromobility_allowed" in available_columns:
        filters.append(f"NOT ({micromobility_allowed} IN ('no', 'false', '0', 'forbidden'))")
    if profile in {"walk", "bike"} or routing_mode == RoutingMode.ACCESSIBLE:
        filters.append(f"{highway} NOT LIKE '%%steps%%'")
    if profile in {"walk", "bike"}:
        filters.append(f"{highway} NOT LIKE '%%motorway%%'")
        filters.append(f"{highway} NOT LIKE '%%trunk%%'")
    return " AND ".join(f"({item})" for item in filters)


def combined_filter_sql(profile: str, base_filter_sql: str, mode: str | RoutingMode, available_columns: set[str]) -> str:
    """Combine profile filters with mode hard-avoid rules."""

    return f"({base_filter_sql}) AND ({hard_avoid_filter_sql(profile, mode, available_columns)})"


def route_attribute_summary_sql(available_columns: set[str]) -> str:
    """Build SQL that aggregates only currently available graph attributes."""

    highway = lower_text_column("highway", available_columns, table_alias="edge")
    surface_type_column = first_available_column(("surface_type", "surface"), available_columns)
    surface_type = lower_first_text_column(("surface_type", "surface"), available_columns, table_alias="edge")
    surface_quality = lower_text_column("surface_quality", available_columns, table_alias="edge")
    sidewalk_presence = lower_text_column("sidewalk_presence", available_columns, table_alias="edge")
    lighting_quality = lower_text_column("lighting_quality", available_columns, table_alias="edge")
    micromobility_allowed = lower_text_column("micromobility_allowed", available_columns, table_alias="edge")
    forbidden_zone = lower_text_column("forbidden_zone", available_columns, table_alias="edge")
    safety_weight = "edge.safety_weight" if "safety_weight" in available_columns else "NULL::DOUBLE PRECISION"
    width = f"COALESCE({numeric_text_column('est_width', available_columns, table_alias='edge')}, {numeric_text_column('width', available_columns, table_alias='edge')})"
    sidewalk_width = numeric_first_text_column(("sidewalk_width_m", "sidewalk_width"), available_columns, table_alias="edge")
    maxspeed = numeric_text_column("maxspeed", available_columns, table_alias="edge")
    lanes = numeric_text_column("lanes", available_columns, table_alias="edge")
    curb_risk = numeric_text_column("curb_risk", available_columns, table_alias="edge")
    curb_frequency = numeric_text_column("curb_frequency", available_columns, table_alias="edge")
    curb_density_per_km = numeric_text_column("curb_density_per_km", available_columns, table_alias="edge")
    crossing_count = numeric_text_column("crossing_count", available_columns, table_alias="edge")
    controlled_crossing_count = numeric_text_column("controlled_crossing_count", available_columns, table_alias="edge")
    uncontrolled_crossing_count = numeric_text_column("uncontrolled_crossing_count", available_columns, table_alias="edge")
    crossing_risk = numeric_text_column("crossing_risk", available_columns, table_alias="edge")
    slope_percent = numeric_first_text_column(("slope_percent", "incline"), available_columns, table_alias="edge")
    traffic_intensity = numeric_text_column("traffic_intensity", available_columns, table_alias="edge")
    pedestrian_density = numeric_text_column("pedestrian_density", available_columns, table_alias="edge")
    micromobility_slow_zone = lower_text_column("micromobility_slow_zone", available_columns, table_alias="edge")
    zone_speed_limit_kmh = numeric_text_column("zone_speed_limit_kmh", available_columns, table_alias="edge")
    road_exposure_proxy = numeric_text_column("road_exposure_proxy", available_columns, table_alias="edge")
    weather_sensitive_risk = numeric_text_column("weather_sensitive_risk", available_columns, table_alias="edge")
    enrichment_confidence = numeric_text_column("enrichment_confidence", available_columns, table_alias="edge")
    telemetry_confidence = numeric_text_column("telemetry_confidence", available_columns, table_alias="edge")
    has_surface = surface_type_column is not None or "surface_quality" in available_columns
    has_sidewalk_presence = "sidewalk_presence" in available_columns
    has_lighting_quality = "lighting_quality" in available_columns
    known_surface_sql = (
        f"{surface_type} IN ('asphalt', 'paving_stones', 'cobblestone', 'gravel', 'dirt') "
        f"OR {surface_quality} IN ('smooth', 'moderate', 'broken')"
    )
    known_lighting_sql = f"{lighting_quality} IN ('poor', 'bad', 'unlit', 'moderate', 'good', 'well_lit')"
    return f"""
        SELECT
            AVG({safety_weight}) AS avg_safety_weight,
            MIN({width}) AS min_width_m,
            MAX({maxspeed}) AS max_speed_kmh,
            MAX({lanes}) AS max_lanes,
            AVG(CASE WHEN {highway} LIKE '%%track%%' THEN 1.0 ELSE 0.0 END) AS track_fraction,
            AVG(CASE WHEN {highway} LIKE '%%cycleway%%' THEN 1.0 ELSE 0.0 END) AS bike_lane_fraction,
            AVG(CASE WHEN {highway} LIKE '%%footway%%' OR {highway} LIKE '%%pedestrian%%' THEN 1.0 ELSE 0.0 END) AS walk_friendly_fraction,
            {optional_average_sql(f"CASE WHEN {surface_type} IN ('cobblestone', 'gravel', 'dirt') OR {surface_quality} = 'broken' THEN 1.0 WHEN {known_surface_sql} THEN 0.0 ELSE NULL END", "bad_surface_fraction", has_surface)},
            {optional_average_sql(f"CASE WHEN {surface_type} = 'asphalt' OR {surface_quality} = 'smooth' THEN 1.0 WHEN {known_surface_sql} THEN 0.0 ELSE NULL END", "smooth_surface_fraction", has_surface)},
            {optional_average_sql(f"CASE WHEN {surface_quality} = 'broken' THEN 1.0 WHEN {surface_quality} IN ('smooth', 'moderate', 'broken') THEN 0.0 ELSE NULL END", "broken_surface_fraction", "surface_quality" in available_columns)},
            {optional_average_sql(f"CASE WHEN {explicit_false_sql(sidewalk_presence)} THEN 1.0 WHEN {explicit_true_sql(sidewalk_presence)} THEN 0.0 ELSE NULL END", "sidewalk_missing_fraction", has_sidewalk_presence)},
            {optional_min_sql(sidewalk_width, "min_sidewalk_width_m", first_available_column(("sidewalk_width_m", "sidewalk_width"), available_columns) is not None)},
            {optional_average_sql(curb_risk, "avg_curb_risk", "curb_risk" in available_columns)},
            {optional_max_sql(curb_frequency, "max_curb_frequency", "curb_frequency" in available_columns)},
            {optional_max_sql(curb_density_per_km, "max_curb_density_per_km", "curb_density_per_km" in available_columns)},
            {optional_sum_sql(crossing_count, "crossing_count", "crossing_count" in available_columns)},
            {optional_sum_sql(controlled_crossing_count, "controlled_crossing_count", "controlled_crossing_count" in available_columns)},
            {optional_sum_sql(uncontrolled_crossing_count, "uncontrolled_crossing_count", "uncontrolled_crossing_count" in available_columns)},
            {optional_average_sql(crossing_risk, "avg_crossing_risk", "crossing_risk" in available_columns)},
            {optional_average_sql(f"CASE WHEN {lighting_quality} IN ('poor', 'bad', 'unlit') THEN 1.0 WHEN {known_lighting_sql} THEN 0.0 ELSE NULL END", "poor_lighting_fraction", has_lighting_quality)},
            {optional_average_sql(f"CASE WHEN {lighting_quality} IN ('good', 'well_lit') THEN 1.0 WHEN {known_lighting_sql} THEN 0.0 ELSE NULL END", "good_lighting_fraction", has_lighting_quality)},
            {optional_max_sql(f"ABS({slope_percent})", "max_slope_percent", first_available_column(("slope_percent", "incline"), available_columns) is not None)},
            {optional_average_sql(traffic_intensity, "avg_traffic_intensity", "traffic_intensity" in available_columns)},
            {optional_average_sql(pedestrian_density, "avg_pedestrian_density", "pedestrian_density" in available_columns)},
            {optional_average_sql(f"CASE WHEN {micromobility_allowed} IN ('no', 'false', '0', 'forbidden') THEN 1.0 WHEN {explicit_true_sql(micromobility_allowed)} THEN 0.0 ELSE NULL END", "micromobility_forbidden_fraction", "micromobility_allowed" in available_columns)},
            {optional_average_sql(f"CASE WHEN {explicit_true_sql(forbidden_zone)} THEN 1.0 WHEN {explicit_false_sql(forbidden_zone)} THEN 0.0 ELSE NULL END", "forbidden_zone_fraction", "forbidden_zone" in available_columns)},
            {optional_average_sql(f"CASE WHEN {explicit_true_sql(micromobility_slow_zone)} THEN 1.0 WHEN {explicit_false_sql(micromobility_slow_zone)} THEN 0.0 ELSE NULL END", "micromobility_slow_zone_fraction", "micromobility_slow_zone" in available_columns)},
            {optional_min_sql(zone_speed_limit_kmh, "min_zone_speed_limit_kmh", "zone_speed_limit_kmh" in available_columns)},
            {optional_average_sql(road_exposure_proxy, "avg_road_exposure_proxy", "road_exposure_proxy" in available_columns)},
            {optional_average_sql(weather_sensitive_risk, "avg_weather_sensitive_risk", "weather_sensitive_risk" in available_columns)},
            {optional_average_sql(enrichment_confidence, "avg_enrichment_confidence", "enrichment_confidence" in available_columns)},
            {optional_average_sql(telemetry_confidence, "avg_telemetry_confidence", "telemetry_confidence" in available_columns)}
        FROM nearest_edges AS edge
    """


def calculate_route_score(summary: RouteAttributeSummary, mode: str | RoutingMode, profile: str) -> RouteScoreResult:
    """Calculate a real route score and explanations from sampled attributes."""

    routing_mode = normalize_route_mode(mode)
    config = SCORING_CONFIGS[routing_mode]
    base_safety = calculate_safety_index(summary.avg_safety_weight)
    score = float(base_safety)
    reasons: list[ScoreReason] = [
        ScoreReason(
            code="safety_weight",
            impact="neutral",
            message="Score is anchored in sampled moscow_network.safety_weight.",
            value=float(summary.avg_safety_weight or 1.0),
            weight=float(base_safety),
        )
    ]
    enrichment_multiplier = enrichment_confidence_multiplier(summary)

    effective_min_width = summary.min_sidewalk_width_m if summary.min_sidewalk_width_m is not None else summary.min_width_m
    if effective_min_width is not None:
        narrow_code = "narrow_sidewalk_width" if summary.min_sidewalk_width_m is not None else "narrow_width"
        medium_code = "medium_sidewalk_width" if summary.min_sidewalk_width_m is not None else "medium_width"
        wide_code = "wide_sidewalk_width" if summary.min_sidewalk_width_m is not None else "wide_width"
        if effective_min_width < 1.2:
            score -= config.narrow_width_score_penalty
            reasons.append(
                ScoreReason(
                    code=narrow_code,
                    impact="penalty",
                    message="Sampled route edges include very narrow width values.",
                    value=effective_min_width,
                    weight=float(config.narrow_width_score_penalty),
                )
            )
        elif effective_min_width < 1.8:
            score -= config.medium_width_score_penalty
            reasons.append(
                ScoreReason(
                    code=medium_code,
                    impact="penalty",
                    message="Sampled route edges include moderately narrow width values.",
                    value=effective_min_width,
                    weight=float(config.medium_width_score_penalty),
                )
            )
        elif effective_min_width >= 3.0:
            score += config.walk_friendly_score_bonus
            reasons.append(
                ScoreReason(
                    code=wide_code,
                    impact="positive",
                    message="Sampled route edges include wide width values.",
                    value=effective_min_width,
                    weight=float(config.walk_friendly_score_bonus),
                )
            )

    if summary.bad_surface_fraction is not None and summary.bad_surface_fraction >= 0.2:
        penalty = confidence_weight(config.bad_surface_score_penalty, enrichment_multiplier)
        score -= penalty
        reasons.append(
            ScoreReason(
                code="bad_surface",
                impact="penalty",
                message="Sampled route edges include cobblestone, gravel, dirt, or broken surface data.",
                value=summary.bad_surface_fraction,
                weight=penalty,
            )
        )
    elif summary.smooth_surface_fraction is not None and summary.smooth_surface_fraction >= 0.5:
        bonus = confidence_weight(config.smooth_surface_score_bonus, enrichment_multiplier)
        score += bonus
        reasons.append(
            ScoreReason(
                code="smooth_surface",
                impact="positive",
                message="A majority of sampled route edges has smooth or asphalt surface data.",
                value=summary.smooth_surface_fraction,
                weight=bonus,
            )
        )

    if profile in {"walk", "bike"} and summary.sidewalk_missing_fraction is not None and summary.sidewalk_missing_fraction >= 0.2:
        penalty = confidence_weight(config.missing_sidewalk_score_penalty, enrichment_multiplier)
        score -= penalty
        reasons.append(
            ScoreReason(
                code="missing_sidewalk",
                impact="penalty",
                message="Sampled route edges explicitly report missing sidewalk presence.",
                value=summary.sidewalk_missing_fraction,
                weight=penalty,
            )
        )

    curb_value = max(summary.avg_curb_risk or 0.0, summary.max_curb_frequency or 0.0, summary.max_curb_density_per_km or 0.0)
    if (summary.avg_curb_risk is not None and summary.avg_curb_risk >= 0.6) or (
        summary.max_curb_frequency is not None and summary.max_curb_frequency >= 5
    ) or (
        summary.max_curb_density_per_km is not None and summary.max_curb_density_per_km >= 10
    ):
        penalty = confidence_weight(config.curb_risk_score_penalty, enrichment_multiplier)
        score -= penalty
        reasons.append(
            ScoreReason(
                code="curb_risk",
                impact="penalty",
                message="Sampled route edges include elevated curb frequency or curb risk data.",
                value=curb_value,
                weight=penalty,
            )
        )

    if (summary.crossing_count is not None and summary.crossing_count >= 6) or (
        summary.avg_crossing_risk is not None and summary.avg_crossing_risk >= 0.5
    ):
        penalty = confidence_weight(config.crossing_score_penalty, enrichment_multiplier)
        score -= penalty
        crossing_value = summary.avg_crossing_risk if summary.avg_crossing_risk is not None else summary.crossing_count
        reasons.append(
            ScoreReason(
                code="many_crossings",
                impact="penalty",
                message="Sampled route edges include real OSM crossing counts or crossing-risk data.",
                value=float(crossing_value or 0.0),
                weight=penalty,
            )
        )

    if summary.poor_lighting_fraction is not None and summary.poor_lighting_fraction >= 0.2:
        penalty = confidence_weight(config.poor_lighting_score_penalty, enrichment_multiplier)
        score -= penalty
        reasons.append(
            ScoreReason(
                code="poor_lighting",
                impact="penalty",
                message="Sampled route edges include poor or missing lighting data.",
                value=summary.poor_lighting_fraction,
                weight=penalty,
            )
        )
    elif summary.good_lighting_fraction is not None and summary.good_lighting_fraction >= 0.6:
        bonus = confidence_weight(config.good_lighting_score_bonus, enrichment_multiplier)
        score += bonus
        reasons.append(
            ScoreReason(
                code="good_lighting",
                impact="positive",
                message="A majority of sampled route edges has good lighting data.",
                value=summary.good_lighting_fraction,
                weight=bonus,
            )
        )

    if summary.max_slope_percent is not None and summary.max_slope_percent >= 8:
        penalty = confidence_weight(config.slope_score_penalty, enrichment_multiplier)
        score -= penalty
        reasons.append(
            ScoreReason(
                code="steep_slope",
                impact="penalty",
                message="Sampled route edges include steep slope or incline values.",
                value=summary.max_slope_percent,
                weight=penalty,
            )
        )

    if summary.avg_traffic_intensity is not None and summary.avg_traffic_intensity >= 0.7:
        penalty = confidence_weight(config.traffic_intensity_score_penalty, enrichment_multiplier)
        score -= penalty
        reasons.append(
            ScoreReason(
                code="traffic_intensity",
                impact="penalty",
                message="Sampled route edges include high traffic intensity data.",
                value=summary.avg_traffic_intensity,
                weight=penalty,
            )
        )
    elif summary.avg_traffic_intensity is not None and summary.avg_traffic_intensity <= 0.25:
        bonus = confidence_weight(config.low_traffic_score_bonus, enrichment_multiplier)
        score += bonus
        reasons.append(
            ScoreReason(
                code="low_traffic",
                impact="positive",
                message="Sampled route edges include low traffic intensity data.",
                value=summary.avg_traffic_intensity,
                weight=bonus,
            )
        )

    if summary.avg_pedestrian_density is not None and summary.avg_pedestrian_density >= 0.8:
        penalty = confidence_weight(config.pedestrian_density_score_penalty, enrichment_multiplier)
        score -= penalty
        reasons.append(
            ScoreReason(
                code="high_pedestrian_density",
                impact="penalty",
                message="Sampled route edges include high pedestrian density data.",
                value=summary.avg_pedestrian_density,
                weight=penalty,
            )
        )

    if profile == "bike" and summary.micromobility_forbidden_fraction is not None and summary.micromobility_forbidden_fraction > 0:
        penalty = confidence_weight(config.micromobility_forbidden_score_penalty, enrichment_multiplier)
        score -= penalty
        reasons.append(
            ScoreReason(
                code="micromobility_forbidden",
                impact="penalty",
                message="Sampled route edges explicitly forbid micromobility.",
                value=summary.micromobility_forbidden_fraction,
                weight=penalty,
            )
        )

    if summary.forbidden_zone_fraction is not None and summary.forbidden_zone_fraction > 0:
        penalty = confidence_weight(config.micromobility_forbidden_score_penalty, enrichment_multiplier)
        score -= penalty
        reasons.append(
            ScoreReason(
                code="forbidden_zone",
                impact="penalty",
                message="Sampled route edges explicitly intersect forbidden-zone data.",
                value=summary.forbidden_zone_fraction,
                weight=penalty,
            )
        )

    if summary.micromobility_slow_zone_fraction is not None and summary.micromobility_slow_zone_fraction > 0:
        penalty = confidence_weight(max(1, round(config.micromobility_forbidden_score_penalty / 2)), enrichment_multiplier)
        score -= penalty
        reasons.append(
            ScoreReason(
                code="micromobility_slow_zone",
                impact="penalty",
                message="Sampled route edges explicitly intersect slow-zone data.",
                value=summary.micromobility_slow_zone_fraction,
                weight=penalty,
            )
        )

    if summary.avg_road_exposure_proxy is not None and summary.avg_road_exposure_proxy >= 0.75:
        score -= config.traffic_score_penalty
        reasons.append(
            ScoreReason(
                code="road_exposure_proxy",
                impact="penalty",
                message="Sampled route edges include a road exposure proxy, not measured traffic intensity.",
                value=summary.avg_road_exposure_proxy,
                weight=float(config.traffic_score_penalty),
            )
        )

    if summary.avg_weather_sensitive_risk is not None and summary.avg_weather_sensitive_risk > 0:
        weather_risk = max(0.0, min(1.0, summary.avg_weather_sensitive_risk))
        weather_confidence = 1.0 if summary.weather_confidence is None else max(0.0, min(1.0, summary.weather_confidence))
        penalty = confidence_weight(config.weather_sensitive_score_penalty, weather_risk * weather_confidence)
        if penalty > 0:
            score -= penalty
            reasons.append(
                ScoreReason(
                    code="weather_sensitive_risk",
                    impact="penalty",
                    message="Real weather data indicates route-level weather risk.",
                    value=weather_risk,
                    weight=penalty,
                )
            )

    if summary.avg_telemetry_confidence is not None and summary.avg_telemetry_confidence >= 0.75:
        score += config.telemetry_confidence_score_bonus
        reasons.append(
            ScoreReason(
                code="telemetry_confidence",
                impact="positive",
                message="Sampled route edges have high telemetry confidence.",
                value=summary.avg_telemetry_confidence,
                weight=float(config.telemetry_confidence_score_bonus),
            )
        )

    traffic_value = max(summary.max_speed_kmh or 0.0, summary.max_lanes or 0.0)
    if (summary.max_speed_kmh is not None and summary.max_speed_kmh >= 60) or (summary.max_lanes is not None and summary.max_lanes >= 4):
        score -= config.traffic_score_penalty
        reasons.append(
            ScoreReason(
                code="high_speed_or_lanes",
                impact="penalty",
                message="Sampled route edges include high maxspeed or many lanes.",
                value=traffic_value,
                weight=float(config.traffic_score_penalty),
            )
        )
    elif summary.max_speed_kmh is not None and summary.max_speed_kmh <= 20:
        score += config.low_speed_score_bonus
        reasons.append(
            ScoreReason(
                code="low_speed",
                impact="positive",
                message="Sampled route edges stay on low-speed streets.",
                value=summary.max_speed_kmh,
                weight=float(config.low_speed_score_bonus),
            )
        )

    if summary.track_fraction >= 0.2:
        score -= config.track_score_penalty
        reasons.append(
            ScoreReason(
                code="track_like_edges",
                impact="penalty",
                message="A notable share of sampled route edges is track-like.",
                value=summary.track_fraction,
                weight=float(config.track_score_penalty),
            )
        )

    if profile == "bike" and summary.bike_lane_fraction >= 0.2:
        score += config.bike_lane_score_bonus
        reasons.append(
            ScoreReason(
                code="cycleway_edges",
                impact="positive",
                message="A notable share of sampled route edges is cycleway-like.",
                value=summary.bike_lane_fraction,
                weight=float(config.bike_lane_score_bonus),
            )
        )

    if profile == "walk" and summary.walk_friendly_fraction >= 0.2:
        score += config.walk_friendly_score_bonus
        reasons.append(
            ScoreReason(
                code="walk_friendly_edges",
                impact="positive",
                message="A notable share of sampled route edges is footway or pedestrian.",
                value=summary.walk_friendly_fraction,
                weight=float(config.walk_friendly_score_bonus),
            )
        )

    total = clamp_score(score)
    return RouteScoreResult(
        mode=routing_mode,
        total=total,
        safety_index=total,
        reasons=tuple(reasons),
        factors={
            "avg_safety_weight": summary.avg_safety_weight,
            "min_width_m": summary.min_width_m,
            "max_speed_kmh": summary.max_speed_kmh,
            "max_lanes": summary.max_lanes,
            "track_fraction": summary.track_fraction,
            "bike_lane_fraction": summary.bike_lane_fraction,
            "walk_friendly_fraction": summary.walk_friendly_fraction,
            "bad_surface_fraction": summary.bad_surface_fraction,
            "smooth_surface_fraction": summary.smooth_surface_fraction,
            "broken_surface_fraction": summary.broken_surface_fraction,
            "sidewalk_missing_fraction": summary.sidewalk_missing_fraction,
            "min_sidewalk_width_m": summary.min_sidewalk_width_m,
            "avg_curb_risk": summary.avg_curb_risk,
            "max_curb_frequency": summary.max_curb_frequency,
            "max_curb_density_per_km": summary.max_curb_density_per_km,
            "crossing_count": summary.crossing_count,
            "controlled_crossing_count": summary.controlled_crossing_count,
            "uncontrolled_crossing_count": summary.uncontrolled_crossing_count,
            "avg_crossing_risk": summary.avg_crossing_risk,
            "poor_lighting_fraction": summary.poor_lighting_fraction,
            "good_lighting_fraction": summary.good_lighting_fraction,
            "max_slope_percent": summary.max_slope_percent,
            "avg_traffic_intensity": summary.avg_traffic_intensity,
            "avg_pedestrian_density": summary.avg_pedestrian_density,
            "micromobility_forbidden_fraction": summary.micromobility_forbidden_fraction,
            "forbidden_zone_fraction": summary.forbidden_zone_fraction,
            "micromobility_slow_zone_fraction": summary.micromobility_slow_zone_fraction,
            "min_zone_speed_limit_kmh": summary.min_zone_speed_limit_kmh,
            "avg_road_exposure_proxy": summary.avg_road_exposure_proxy,
            "avg_weather_sensitive_risk": summary.avg_weather_sensitive_risk,
            "weather_confidence": summary.weather_confidence,
            "avg_enrichment_confidence": summary.avg_enrichment_confidence,
            "avg_telemetry_confidence": summary.avg_telemetry_confidence,
        },
    )
