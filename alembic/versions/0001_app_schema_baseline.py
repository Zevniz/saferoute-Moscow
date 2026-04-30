"""App-owned telemetry and enrichment baseline.

Revision ID: 0001_app_schema_baseline
Revises: None
Create Date: 2026-04-25
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0001_app_schema_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create app-owned schema objects without destroying existing data."""

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sidewalk_samples (
            id BIGSERIAL PRIMARY KEY,
            device_id TEXT NOT NULL,
            captured_at TIMESTAMPTZ NOT NULL,
            lat DOUBLE PRECISION NOT NULL,
            lon DOUBLE PRECISION NOT NULL,
            speed_mps DOUBLE PRECISION NOT NULL,
            source TEXT NOT NULL,
            surface_score DOUBLE PRECISION,
            vibration_rms DOUBLE PRECISION,
            obstacle_score DOUBLE PRECISION,
            gps_accuracy_m DOUBLE PRECISION,
            model_version TEXT,
            h3_cell TEXT NOT NULL,
            h3_resolution INTEGER NOT NULL,
            quality_score DOUBLE PRECISION NOT NULL,
            confidence DOUBLE PRECISION NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sidewalk_cell_aggregates (
            h3_cell TEXT NOT NULL,
            h3_resolution INTEGER NOT NULL,
            centroid_lat DOUBLE PRECISION NOT NULL,
            centroid_lon DOUBLE PRECISION NOT NULL,
            sample_count INTEGER NOT NULL DEFAULT 0,
            quality_sum DOUBLE PRECISION NOT NULL DEFAULT 0,
            obstacle_sum DOUBLE PRECISION NOT NULL DEFAULT 0,
            vibration_sum DOUBLE PRECISION NOT NULL DEFAULT 0,
            confidence_sum DOUBLE PRECISION NOT NULL DEFAULT 0,
            first_seen_at TIMESTAMPTZ NOT NULL,
            last_seen_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (h3_cell, h3_resolution)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS sidewalk_samples_captured_at_idx ON sidewalk_samples (captured_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS sidewalk_samples_h3_idx ON sidewalk_samples (h3_resolution, h3_cell)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS sidewalk_cell_aggregates_bbox_idx "
        "ON sidewalk_cell_aggregates (h3_resolution, centroid_lon, centroid_lat)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS safety_enrichment_datasets (
            dataset_version TEXT PRIMARY KEY,
            source_name TEXT NOT NULL,
            source_url TEXT,
            source_checksum TEXT,
            imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            valid_from TIMESTAMPTZ,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            is_active BOOLEAN NOT NULL DEFAULT false
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS safety_edge_enrichment (
            edge_id BIGINT NOT NULL,
            dataset_version TEXT NOT NULL REFERENCES safety_enrichment_datasets(dataset_version) ON DELETE RESTRICT,
            source_name TEXT NOT NULL,
            confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
            observed_at TIMESTAMPTZ,
            surface_type TEXT CHECK (surface_type IS NULL OR surface_type IN ('asphalt', 'paving_stones', 'cobblestone', 'gravel', 'dirt')),
            surface_quality TEXT CHECK (surface_quality IS NULL OR surface_quality IN ('smooth', 'moderate', 'broken')),
            sidewalk_presence BOOLEAN,
            sidewalk_width_m DOUBLE PRECISION CHECK (sidewalk_width_m IS NULL OR sidewalk_width_m >= 0),
            curb_risk DOUBLE PRECISION CHECK (curb_risk IS NULL OR (curb_risk >= 0 AND curb_risk <= 1)),
            curb_frequency DOUBLE PRECISION CHECK (curb_frequency IS NULL OR curb_frequency >= 0),
            crossing_count INTEGER CHECK (crossing_count IS NULL OR crossing_count >= 0),
            lighting_quality TEXT CHECK (lighting_quality IS NULL OR lighting_quality IN ('poor', 'moderate', 'good')),
            slope_percent DOUBLE PRECISION,
            traffic_intensity DOUBLE PRECISION CHECK (traffic_intensity IS NULL OR (traffic_intensity >= 0 AND traffic_intensity <= 1)),
            pedestrian_density DOUBLE PRECISION CHECK (pedestrian_density IS NULL OR (pedestrian_density >= 0 AND pedestrian_density <= 1)),
            micromobility_allowed BOOLEAN,
            forbidden_zone BOOLEAN,
            weather_sensitive_risk DOUBLE PRECISION CHECK (weather_sensitive_risk IS NULL OR (weather_sensitive_risk >= 0 AND weather_sensitive_risk <= 1)),
            telemetry_confidence DOUBLE PRECISION CHECK (telemetry_confidence IS NULL OR (telemetry_confidence >= 0 AND telemetry_confidence <= 1)),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (edge_id, dataset_version)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS safety_edge_enrichment_edge_idx ON safety_edge_enrichment (edge_id)")
    op.execute("CREATE INDEX IF NOT EXISTS safety_edge_enrichment_dataset_idx ON safety_edge_enrichment (dataset_version)")
    op.execute("CREATE INDEX IF NOT EXISTS safety_enrichment_datasets_active_idx ON safety_enrichment_datasets (is_active) WHERE is_active")


def downgrade() -> None:
    """No-op by design: the public-launch baseline must not drop production data."""

    pass
