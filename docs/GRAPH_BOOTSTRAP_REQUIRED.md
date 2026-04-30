# Graph Bootstrap Requirement

SafeRoute must not run public self-hosted routing from an undocumented Docker volume. A fresh server needs one real graph source for `public.moscow_network`.

## Accepted Sources

Use one of:

- `SOURCE_DATABASE_URL`: a real PostGIS database that contains `public.moscow_network`;
- `SAFEROUTE_GRAPH_DUMP_PATH` or legacy `GRAPH_DUMP_FILE`: a custom-format `pg_dump` created by `npm run db:graph-export`, plus the matching `.manifest.json`.

Current local verified artifact path:

- path: `data/graph/moscow_network.dump`

Use the manifest as the checksum source of truth:

```bash
SAFEROUTE_GRAPH_DUMP_PATH=data/graph/moscow_network.dump npm run db:graph-dump-check
```

`data/graph/moscow_network.dump` is treated as a real local artifact, not generated sample data. For public launch, publish this artifact or an equivalent official source in a controlled storage location with the manifest and checksum.

Required table columns:

- `id`
- `u`
- `v`
- `highway`
- `length`
- `safety_weight`
- `geometry` with SRID `4326`

Prepared outputs after restore/import:

- `cost_walk_safe`
- `cost_bike_safe`
- `cost_car_safe`
- `source_x`
- `source_y`
- `target_x`
- `target_y`
- `public.moscow_network_nodes`

## Commands

Validate source availability:

```bash
npm run bootstrap:check
npm run db:graph-source-check
```

Export a reproducible dump from a known-good database:

```bash
DATABASE_URL=postgresql://... npm run db:graph-export
```

Restore into a target database:

```bash
SAFEROUTE_GRAPH_DUMP_PATH=data/graph/moscow_network.dump npm run db:graph-restore
```

Run an isolated fresh bootstrap test:

```bash
npm run bootstrap:fresh
```

This starts a separate compose project and isolated volumes. It does not remove the working self-hosted volumes.

If no real source exists, these commands fail with `GRAPH_BOOTSTRAP_REQUIRED`. They do not generate fake graph rows.

## OSM PBF Caveat

`data/osm/moscow-oblast.osm.pbf` is a real Geofabrik-derived raw source used by Valhalla. It is not, by itself, a verified reproducer for the current `public.moscow_network` table until a graph-builder with stable edge provenance exists.
