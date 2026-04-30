# Public Beta Release Notes

SafeRoute is a public beta safety-first navigator for Moscow micromobility. It uses real Valhalla/PostGIS routes and active OpenStreetMap-derived enrichment for surface, surface quality, sidewalk presence, lighting tags, sparse numeric slope data, and direct OSM crossing way counts. Advanced safety layers for curb risk, measured traffic, pedestrian density, micromobility zones, production weather risk, and telemetry confidence are not active by default and do not affect scoring unless a real validated source/provider is enabled.

## What Works

- Real walk, bike, and car routing through FastAPI, Valhalla, PostGIS, and pgRouting.
- Photon search/reverse geocoding through the SafeRoute API.
- Published graph artifact and verified fresh restore from the real Moscow graph dump.
- Active additive OSM-derived enrichment joined directly through `public.moscow_network.osmid`.
- Optional Open-Meteo weather risk integration is implemented behind `SAFEROUTE_WEATHER_ENABLED=true`; default runtime makes no weather calls.
- Route score metadata in `properties.score.data_sources.enrichment`.
- Visible OSM/CARTO attribution in the map UI.
- Self-hosted smoke, route corpus, e2e, and browser QA pass against real local services.

## Active Enrichment

| Field | Value |
|---|---|
| Dataset | `osm-moscow-oblast-tags-20260419` |
| Source | OpenStreetMap way tags via Geofabrik Central Federal District extract |
| Source URL | https://download.geofabrik.de/russia/central-fed-district.html |
| License | ODbL 1.0; attribution required |
| Source checksum | `sha256:939e71c748e20c75b020b05fbbddb10f0f627f54daf168210af72056669118da` |
| Imported rows | `1,126,588` |
| Average confidence | `0.89` |
| Mapping | Direct OSM way IDs from `public.moscow_network.osmid`; no spatial guessing |

| Field | Value |
|---|---|
| Dataset | `osm-moscow-oblast-crossings-20260419` |
| Source | OpenStreetMap crossing way tags via Geofabrik Central Federal District extract |
| Source URL | https://download.geofabrik.de/russia/central-fed-district.html |
| License | ODbL 1.0; attribution required |
| Source checksum | `sha256:939e71c748e20c75b020b05fbbddb10f0f627f54daf168210af72056669118da` |
| Generated CSV checksum | `sha256:eb5adb84c83f1917d4e0b0ecb8db3ef70be164d00c0889ee9039b0f133ec3931` |
| Imported rows | `62,328` |
| Average confidence | `0.909` |
| Mapping | Direct OSM way IDs from `public.moscow_network.osmid`; point/node crossings are not guessed |

Active factors:

| Factor | Rows | Notes |
|---|---:|---|
| `surface_type` | `1,047,856` | OSM `surface` values normalized to supported enums. |
| `surface_quality` | `101,604` | OSM `smoothness`; unknown values stay blank. |
| `sidewalk_presence` | `12,424` | Direct sidewalk tags only; sparse coverage. |
| `lighting_quality` | `492,436` | OSM `lit` tag-derived, not measured illumination. |
| `slope_percent` | `452` | Numeric percent OSM `incline` only. |
| `crossing_count` | `62,328` | Direct OSM crossing ways only. |
| `controlled_crossing_count` | `62,328` | Tag-derived controlled/signalized/marked counts. |
| `uncontrolled_crossing_count` | `62,328` | Tag-derived uncontrolled/unknown counts. |
| `crossing_risk` | `62,328` | Conservative tag-derived risk; no node guessing. |

## Known Limitations

SafeRoute must not be marketed as a full public safety launch yet. These factors are not active and must not appear as active claims:

- curb risk / curb density
- measured traffic intensity
- pedestrian density
- micromobility forbidden/slow zones
- weather-sensitive risk by default; Open-Meteo can be enabled explicitly
- telemetry confidence

Inactive factors remain `null` or absent in API score factors and reasons. Missing data does not create penalties, bonuses, or UI claims.

## Verification Summary

The public beta package is considered valid only when these commands pass against the intended local/self-hosted stack:

```bash
bash -n scripts/*.sh scripts/data/*.sh
node -e "JSON.parse(require('fs').readFileSync('package.json','utf8'))"
docker compose config
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker compose build api frontend
npm run build
npm run check:backend
npm run check:full
npm run db:enrichment-check
npm run db:enrichment-report
npm run smoke:api
npm run smoke:self-hosted
npm run route:corpus-check
APP_URL=http://127.0.0.1:5173 npm run test:e2e
```

Expected enrichment result:

- active datasets: `osm-moscow-oblast-tags-20260419` and `osm-moscow-oblast-crossings-20260419`;
- nonzero rows for surface, surface quality, sidewalk presence, lighting, sparse slope, and crossing factors;
- zero rows for curb, measured traffic, pedestrian density, micromobility, default weather, and telemetry confidence.

## Production Deployment Checklist

- Set production API keys in the deployment secret manager; do not commit secrets.
- Enable rate limits and configure endpoint-specific buckets where needed.
- Protect deep health, metrics, tiles, and telemetry writes according to `docs/SECURITY_PRODUCTION_ENV.md`.
- Configure graph artifact restore from the published real dump and manifest.
- Apply migrations and telemetry/enrichment schema checks before public traffic.
- Preserve visible OSM/CARTO attribution in the frontend.
- Include ODbL attribution and derived-data notes in distribution/release materials.
- Run the full verification command set after deployment config is applied.
