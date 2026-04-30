# Graph Data Quality

SafeRoute routing depends on real `public.moscow_network` data in PostGIS. The project does not create fake graph data.

## Read-Only Check

Run target graph verification:

```bash
npm run db:graph-check
```

The command selects the reachable compose database on `127.0.0.1:5434` when available, otherwise the local host database URL. Override with:

```bash
DATABASE_URL=postgresql://user:pass@host:5432/db npm run db:graph-check
```

It fails if production-critical assets are missing:

- PostGIS and pgRouting extensions.
- `public.moscow_network`.
- Required columns: `id`, `u`, `v`, `highway`, `length`, `safety_weight`, `geometry`.
- Non-empty graph rows.
- Non-null geometry for every row.
- SRID `4326`.
- Prepared routing/A* columns.
- `public.moscow_network_nodes`.
- Required graph indexes.

It also prints current scoring-column coverage, safety-weight distribution, top highway values, and optional enrichment columns.

Run source graph verification before a fresh import:

```bash
SOURCE_DATABASE_URL=postgresql://user:pass@host:5432/db npm run db:graph-source-check
```

`db:graph-source-check` is read-only. It verifies that the source has PostGIS, `public.moscow_network`, required base columns, rows, non-null geometry, SRID `4326`, populated `safety_weight`, and routing-prep eligible length/geometry values. It does not require prepared cost columns or `moscow_network_nodes`; those are created in the target by `scripts/prepare-production-db.sql`.

## Verified Local Graph

The current self-hosted graph has:

- `1,579,570` `public.moscow_network` rows.
- Geometry on every row.
- SRID `4326`.
- `public.moscow_network_nodes`.
- PostGIS and pgRouting enabled.
- Prepared routing columns: `cost_walk_safe`, `cost_bike_safe`, `cost_car_safe`, `source_x`, `source_y`, `target_x`, `target_y`.

Current real scoring coverage:

- `safety_weight`: present on every edge.
- `width`: sparse.
- `est_width`: very sparse.
- `maxspeed`: partial.
- `lanes`: partial.
- `access`: sparse.
- Expanded product factors such as surface, sidewalk presence, lighting, slope, curb risk, pedestrian density, weather risk, and telemetry confidence are not present as graph columns in the verified local DB.

## Data Requirements

Full product scoring needs real enrichment data before the backend can use those signals:

- surface type and quality
- sidewalk presence and width
- curb frequency/risk
- crossing counts
- lighting quality
- slope/incline
- traffic intensity
- pedestrian density
- micromobility/forbidden zones
- weather-sensitive risk
- telemetry confidence along routes

Until these data sources exist, SafeRoute must keep these factors inactive and must not infer them from unrelated fields.

## Fresh Bootstrap And Recovery

A fresh DB volume does not contain `public.moscow_network` unless a real source is imported. Use:

```bash
npm run self-hosted:preflight
npm run bootstrap:self-hosted
```

`SOURCE_DATABASE_URL` must point to a real database containing `public.moscow_network`, or the bootstrap process needs a real dump/import source. Do not create placeholder rows to satisfy graph checks.

Recommended dump format:

```bash
pg_dump "$SOURCE_DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-privileges \
  --table=public.moscow_network \
  --file=data/graph/moscow_network.dump
```

Restoring a dump into a target DB must be followed by:

```bash
psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/prepare-production-db.sql
DATABASE_URL="$TARGET_DATABASE_URL" npm run db:graph-check
```
