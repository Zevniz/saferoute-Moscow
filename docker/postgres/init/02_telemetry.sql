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
);

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
);

CREATE INDEX IF NOT EXISTS sidewalk_samples_captured_at_idx ON sidewalk_samples (captured_at DESC);
CREATE INDEX IF NOT EXISTS sidewalk_samples_h3_idx ON sidewalk_samples (h3_resolution, h3_cell);
CREATE INDEX IF NOT EXISTS sidewalk_cell_aggregates_bbox_idx ON sidewalk_cell_aggregates (h3_resolution, centroid_lon, centroid_lat);
