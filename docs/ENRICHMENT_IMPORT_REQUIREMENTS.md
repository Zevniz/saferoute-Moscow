# Enrichment Import Requirements

SafeRoute can import real per-edge enrichment data only when every row is mapped to `public.moscow_network.id` or produced by a deterministic audited join.

## Built-In OSM Import

The first production-capable import path is OSM-derived:

```bash
ACTIVATE_ENRICHMENT=true npm run db:enrichment-import:osm
```

It reads `data/osm/moscow-oblast.osm.pbf`, extracts OSM way tags with `osmium`, maps them through `public.moscow_network.osmid`, writes an ignored CSV under `data/enrichment/osm/`, validates it, and imports it through the generic CSV importer.

Supported OSM factors:

- `surface_type` from `surface`
- `surface_quality` from `smoothness`
- `sidewalk_presence` from `sidewalk`, `sidewalk:left`, `sidewalk:right`
- `lighting_quality` from `lit`
- `slope_percent` from numeric-percent `incline`

Unsupported values and conflicting multi-way values are omitted, not guessed.

The advanced OSM import path supports validation-gated direct way mapping:

```bash
npm run db:enrichment-import:crossings-osm
npm run db:enrichment-import:curb-osm
```

Crossing ways currently pass validation and are active. Curb features are extracted and reported, but they remain inactive because the current real source does not meet the coverage/ambiguity activation threshold.

## Generic CSV Format

Required columns:

- `edge_id`: positive `public.moscow_network.id`
- `confidence`: `0..1`

Optional columns:

- `observed_at`
- `surface_type`: `asphalt`, `paving_stones`, `cobblestone`, `gravel`, `dirt`
- `surface_quality`: `smooth`, `moderate`, `broken`
- `sidewalk_presence`: boolean
- `sidewalk_width_m`: meters, `>= 0`
- `curb_risk`: `0..1`
- `curb_frequency`: `>= 0`
- `curb_density_per_km`: `>= 0`
- `crossing_count`: integer, `>= 0`
- `controlled_crossing_count`: integer, `>= 0`
- `uncontrolled_crossing_count`: integer, `>= 0`
- `crossing_risk`: `0..1`
- `lighting_quality`: `poor`, `moderate`, `good`
- `slope_percent`: numeric
- `traffic_intensity`: `0..1`
- `pedestrian_density`: `0..1`
- `micromobility_allowed`: boolean
- `forbidden_zone`: boolean
- `micromobility_slow_zone`: boolean
- `zone_speed_limit_kmh`: `>= 0`
- `road_exposure_proxy`: `0..1`, and must not be labeled as measured traffic
- `weather_sensitive_risk`: `0..1`
- `telemetry_confidence`: `0..1`

Blank optional values mean unavailable.

## Activation Requirements

`ACTIVATE_ENRICHMENT=true` requires:

- `SOURCE_NAME`
- `DATASET_VERSION`
- `SOURCE_CHECKSUM`
- at least one real factor column populated
- every `edge_id` must exist in `public.moscow_network`

Example:

```bash
ENRICHMENT_FILE=/secure/sources/moscow-edge-enrichment.csv \
DATASET_VERSION=vendor-or-survey-YYYY-MM \
SOURCE_NAME=<real-source-name> \
SOURCE_URL=<source-card-url> \
SOURCE_CHECKSUM=sha256:<checksum> \
SOURCE_METADATA_FILE=/secure/sources/source-card.json \
ACTIVATE_ENRICHMENT=true \
npm run db:enrichment-import
```

## Validation

Run:

```bash
npm run db:enrichment-check
npm run db:enrichment-report
npm run route:corpus-check
```

The importer rejects invalid enum values, out-of-range numeric values, invalid booleans, empty files, missing provenance for activation, missing graph edge IDs, and active files with no populated factor columns.

## Source Quality Policy

Accepted:

- Direct `edge_id` mapping.
- Direct OSM way ID mapping through `public.moscow_network.osmid`.
- Spatial joins only with documented geometry thresholds, ambiguity reporting, and manual sample review.
- OSM curb activation additionally requires at least `1,000` accepted source features, at least `1,000` imported edge rows, ambiguous rate `<= 0.15`, p95 distance `<= 5m`, median distance `<= 2.5m`, plausible edge rate `>= 0.90`, incompatible edge rate `<= 0.05`, and sample match output.

Rejected:

- Synthetic values.
- Filling unknowns with defaults.
- Treating OSM `maxspeed`/`lanes` as measured `traffic_intensity`.
- Treating sparse OSM node tags as per-edge curb/crossing data without a tested aggregation pipeline.
