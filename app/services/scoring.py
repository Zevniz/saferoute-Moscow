"""Mode-aware SafeRoute scoring primitives.

This module intentionally uses only attributes that are present in the current
`public.moscow_network` graph. Missing future data such as lighting, slope,
surface quality, curb density, and sidewalk presence is documented separately
and is not inferred here.
"""

from __future__ import annotations

from dataclasses import dataclass
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

    def to_public_dict(self) -> dict[str, object]:
        """Return a backward-compatible additive API payload."""

        return {
            "mode": self.mode.value,
            "total": self.total,
            "safety_index": self.safety_index,
            "factors": self.factors,
            "reasons": [reason.to_public_dict() for reason in self.reasons],
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


def _qualified_column(column: str, table_alias: str | None) -> str:
    if table_alias:
        return f"{table_alias}.{column}"
    return column


def lower_text_column(column: str, available_columns: set[str], table_alias: str | None = None) -> str:
    """Return a lowercase SQL expression for an optional text graph column."""

    if column in available_columns:
        qualified = _qualified_column(column, table_alias)
        return f"LOWER(COALESCE({qualified}, ''))"
    return "''"


def numeric_text_column(column: str, available_columns: set[str], table_alias: str | None = None) -> str:
    """Return a numeric SQL expression for optional text numeric graph columns."""

    if column not in available_columns:
        return "NULL::DOUBLE PRECISION"
    qualified = _qualified_column(column, table_alias)
    return f"""
        CASE
            WHEN {qualified} ~ '^[0-9]+(\\.[0-9]+)?$' THEN {qualified}::DOUBLE PRECISION
            ELSE NULL::DOUBLE PRECISION
        END
    """


def route_comfort_multiplier_sql(profile: str, mode: str | RoutingMode, available_columns: set[str]) -> str:
    """Build a real-data safety multiplier from available graph attributes."""

    routing_mode = normalize_route_mode(mode)
    config = SCORING_CONFIGS[routing_mode]
    highway = lower_text_column("highway", available_columns)
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
                WHEN {width} IS NOT NULL AND {width} < 1.2 THEN {config.narrow_width_cost_penalty}
                WHEN {width} IS NOT NULL AND {width} < 1.8 THEN {config.medium_width_cost_penalty}
                WHEN {width} IS NOT NULL AND {width} >= 3.0 THEN 0.86
                ELSE 1.0
              END
            * CASE
                WHEN {maxspeed} IS NOT NULL AND {maxspeed} >= 60 THEN {config.traffic_cost_penalty}
                WHEN {lanes} IS NOT NULL AND {lanes} >= 4 THEN {config.traffic_cost_penalty}
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
    filters = [forbidden_access_filter_sql(available_columns)]
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
    safety_weight = "edge.safety_weight" if "safety_weight" in available_columns else "NULL::DOUBLE PRECISION"
    width = f"COALESCE({numeric_text_column('est_width', available_columns, table_alias='edge')}, {numeric_text_column('width', available_columns, table_alias='edge')})"
    maxspeed = numeric_text_column("maxspeed", available_columns, table_alias="edge")
    lanes = numeric_text_column("lanes", available_columns, table_alias="edge")
    return f"""
        SELECT
            AVG({safety_weight}) AS avg_safety_weight,
            MIN({width}) AS min_width_m,
            MAX({maxspeed}) AS max_speed_kmh,
            MAX({lanes}) AS max_lanes,
            AVG(CASE WHEN {highway} LIKE '%%track%%' THEN 1.0 ELSE 0.0 END) AS track_fraction,
            AVG(CASE WHEN {highway} LIKE '%%cycleway%%' THEN 1.0 ELSE 0.0 END) AS bike_lane_fraction,
            AVG(CASE WHEN {highway} LIKE '%%footway%%' OR {highway} LIKE '%%pedestrian%%' THEN 1.0 ELSE 0.0 END) AS walk_friendly_fraction
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

    if summary.min_width_m is not None:
        if summary.min_width_m < 1.2:
            score -= config.narrow_width_score_penalty
            reasons.append(
                ScoreReason(
                    code="narrow_width",
                    impact="penalty",
                    message="Sampled route edges include very narrow width values.",
                    value=summary.min_width_m,
                    weight=float(config.narrow_width_score_penalty),
                )
            )
        elif summary.min_width_m < 1.8:
            score -= config.medium_width_score_penalty
            reasons.append(
                ScoreReason(
                    code="medium_width",
                    impact="penalty",
                    message="Sampled route edges include moderately narrow width values.",
                    value=summary.min_width_m,
                    weight=float(config.medium_width_score_penalty),
                )
            )
        elif summary.min_width_m >= 3.0:
            score += config.walk_friendly_score_bonus
            reasons.append(
                ScoreReason(
                    code="wide_width",
                    impact="positive",
                    message="Sampled route edges include wide width values.",
                    value=summary.min_width_m,
                    weight=float(config.walk_friendly_score_bonus),
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
        },
    )
