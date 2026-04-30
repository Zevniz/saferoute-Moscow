"""Add nullable advanced enrichment columns.

Revision ID: 0002_advanced_enrichment_columns
Revises: 0001_app_schema_baseline
Create Date: 2026-04-27
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002_advanced_enrichment_columns"
down_revision: Union[str, None] = "0001_app_schema_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Extend app-owned enrichment rows without changing existing data."""

    op.execute(
        """
        ALTER TABLE safety_edge_enrichment
          ADD COLUMN IF NOT EXISTS curb_density_per_km DOUBLE PRECISION,
          ADD COLUMN IF NOT EXISTS controlled_crossing_count INTEGER,
          ADD COLUMN IF NOT EXISTS uncontrolled_crossing_count INTEGER,
          ADD COLUMN IF NOT EXISTS crossing_risk DOUBLE PRECISION,
          ADD COLUMN IF NOT EXISTS micromobility_slow_zone BOOLEAN,
          ADD COLUMN IF NOT EXISTS zone_speed_limit_kmh DOUBLE PRECISION,
          ADD COLUMN IF NOT EXISTS road_exposure_proxy DOUBLE PRECISION
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'safety_edge_enrichment_curb_density_per_km_check'
          ) THEN
            ALTER TABLE safety_edge_enrichment
              ADD CONSTRAINT safety_edge_enrichment_curb_density_per_km_check
              CHECK (curb_density_per_km IS NULL OR curb_density_per_km >= 0);
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'safety_edge_enrichment_controlled_crossing_count_check'
          ) THEN
            ALTER TABLE safety_edge_enrichment
              ADD CONSTRAINT safety_edge_enrichment_controlled_crossing_count_check
              CHECK (controlled_crossing_count IS NULL OR controlled_crossing_count >= 0);
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'safety_edge_enrichment_uncontrolled_crossing_count_check'
          ) THEN
            ALTER TABLE safety_edge_enrichment
              ADD CONSTRAINT safety_edge_enrichment_uncontrolled_crossing_count_check
              CHECK (uncontrolled_crossing_count IS NULL OR uncontrolled_crossing_count >= 0);
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'safety_edge_enrichment_crossing_risk_check'
          ) THEN
            ALTER TABLE safety_edge_enrichment
              ADD CONSTRAINT safety_edge_enrichment_crossing_risk_check
              CHECK (crossing_risk IS NULL OR (crossing_risk >= 0 AND crossing_risk <= 1));
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'safety_edge_enrichment_zone_speed_limit_kmh_check'
          ) THEN
            ALTER TABLE safety_edge_enrichment
              ADD CONSTRAINT safety_edge_enrichment_zone_speed_limit_kmh_check
              CHECK (zone_speed_limit_kmh IS NULL OR zone_speed_limit_kmh >= 0);
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'safety_edge_enrichment_road_exposure_proxy_check'
          ) THEN
            ALTER TABLE safety_edge_enrichment
              ADD CONSTRAINT safety_edge_enrichment_road_exposure_proxy_check
              CHECK (road_exposure_proxy IS NULL OR (road_exposure_proxy >= 0 AND road_exposure_proxy <= 1));
          END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS safety_edge_enrichment_active_factor_idx
        ON safety_edge_enrichment (dataset_version, edge_id)
        """
    )


def downgrade() -> None:
    """No-op by design: public release migrations must not drop production data."""

    pass
