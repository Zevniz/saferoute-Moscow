# Official Micromobility Zones

SafeRoute treats Moscow micromobility forbidden and slow zones as a fail-closed advanced safety layer. The schema and scoring hooks are ready, but the layer must remain inactive until a real, legal, reproducible polygon source is imported and validated.

Launch-safe wording while inactive:

> Official micromobility forbidden/slow zones remain inactive because no legally usable, reproducible edge-mappable Moscow zone dataset is available yet.

## Source Evaluation

| Candidate | Decision | Reason |
|---|---|---|
| Moscow Transport slow-zones page, `https://transport.mos.ru/kicksharing/slow-zones` | Pipeline candidate, not active | Official page confirms slow/prohibited SIM zones, but it is not a verified downloadable polygon dataset by itself. |
| Moscow open data portal, `https://data.mos.ru/` | Search candidate, not active | Official/legal if a matching polygon dataset is published. No local source file or documented dataset is currently present in the repo. |
| Operator app/API geofences | Rejected unless an operator publishes a licensed export | App-visible zones and private APIs must not be scraped or reverse engineered. |
| OSM access/bicycle tags and `overpass_moscow_micromobility_candidates.ql` | Rejected for official zones | OSM is legal ODbL data, but these tags are not official scooter forbidden/slow-zone polygons. They must not be marketed as operator or city SIM zones. |
| Local repo/data files | Inactive | The repo contains only an OSM/Overpass candidate query, not production zone polygons. |

## Import Contract

Use:

```bash
MICROMOBILITY_ZONES_FILE=/path/to/official-zones.geojson \
DATASET_VERSION=moscow-micromobility-zones-YYYYMMDD \
SOURCE_NAME=official-moscow-micromobility-zones \
SOURCE_OWNER="source owner" \
SOURCE_URL="https://official/source/or/local/path" \
SOURCE_LICENSE="license or terms" \
SOURCE_CHECKSUM=sha256:<checksum> \
ACTIVATE_ENRICHMENT=false \
npm run db:enrichment-import:micromobility-zones
```

Supported production formats for v1 are GeoJSON FeatureCollection files and GeoPackage files convertible by `ogr2ogr`. Test fixtures may exist only under `tests/fixtures` and the importer refuses to activate them.

Required feature properties:

| Property | Required | Notes |
|---|---:|---|
| `zone_type` | yes | One of `forbidden`, `slow`, `preferred`, `dedicated`. |
| `confidence` | yes | Numeric `0..1`, supplied by source/import policy. |
| `zone_speed_limit_kmh` | for `slow` | Required for slow zones. |
| `source_id` | recommended | Used for audit traceability when available. |

## Validation Gates

Activation is allowed only when all gates pass:

- source owner, source URL/path, license/terms, dataset version, and checksum are present;
- checksum matches the source file;
- geometry is Polygon/MultiPolygon, valid, non-empty, and EPSG:4326/CRS84 or normalized to EPSG:4326;
- zone type is explicit;
- slow zones include a speed limit;
- zones intersect `public.moscow_network`;
- resulting edge rows are written idempotently into `safety_edge_enrichment`;
- `db:enrichment-report` shows active micromobility rows only after `ACTIVATE_ENRICHMENT=true`;
- route/API/UI tests prove reasons and warnings appear only when active rows exist.

## Mapping And Scoring

The importer maps official polygons to `public.moscow_network` by `ST_Intersects(edge.geometry, zone.geom)`.

Scored v1 mapping:

| Source zone | Enrichment fields | Scoring behavior |
|---|---|---|
| `forbidden` | `micromobility_allowed=false`, `forbidden_zone=true` | Hard/severe penalty and bike/micromobility avoidance where real active data intersects sampled edges. |
| `slow` | `micromobility_slow_zone=true`, `zone_speed_limit_kmh=<value>` | Slow-zone penalty and source-aware reason where real active data intersects sampled edges. |
| `preferred`, `dedicated` | metadata only in v1 | Accepted for future expansion, but not scored unless a real scoring field is added. |

Missing zones never mean an area is safe or unrestricted. They simply mean SafeRoute lacks verified official zone data for that edge.
