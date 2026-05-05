"""Shared constants for SafeRoute routing and scoring."""

from __future__ import annotations

from typing import Final

# Base graph columns that may exist in moscow_network
BASE_SCORING_COLUMNS: Final[tuple[str, ...]] = (
    "id",
    "highway",
    "safety_weight",
    "width",
    "est_width",
    "maxspeed",
    "lanes",
    "access",
)

# Enrichment columns that may exist in safety_edge_enrichment (or overlayed on moscow_network)
ENRICHMENT_SCORING_COLUMNS: Final[tuple[str, ...]] = (
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
)

# All scoring-related columns (used for validation)
ALL_SCORING_COLUMNS: Final[tuple[str, ...]] = BASE_SCORING_COLUMNS + ENRICHMENT_SCORING_COLUMNS
