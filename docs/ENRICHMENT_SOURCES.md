# Enrichment Sources

## Source Package And PBF Validation

- Source package inspected: `data/enrichment/source_packs/saferoute_moscow_data_pack`
- Source inventory: `moscow_enrichment_sources.csv`
- Query references inspected: `queries/overpass_moscow_curbs.ql`, `queries/overpass_moscow_oblast_curbs.ql`, `queries/overpass_moscow_crossings.ql`, `queries/overpass_moscow_sidewalks.ql`, `queries/overpass_moscow_micromobility_candidates.ql`
- Primary source used for import: `data/osm/moscow-oblast.osm.pbf`
- Rejected source: partial `data/osm/central-fed-district-latest.osm.pbf` was renamed to a `.partial.bad.*` file and was not used.
- File size: `384,279,036` bytes
- Osmium validation: `osmium fileinfo -e data/osm/moscow-oblast.osm.pbf`
- Bbox: `(33.2780674,52.5405026,48.9822685,59.224111)`, covering Moscow and Moscow Oblast.
- Latest OSM timestamp in file: `2026-04-19T20:19:54Z`
- Source checksum: `sha256:939e71c748e20c75b020b05fbbddb10f0f627f54daf168210af72056669118da`

Offline sample extraction from the validated PBF confirmed real source tags:

| Candidate | Extracted objects |
|---|---:|
| `highway=crossing` | `72,649` |
| curb/kerb filters | `43,803` |
| sidewalk filters | `11,948` |
| surface tags | `614,241` |
| `lit` tags | `196,662` |
| `incline` tags | `20,699` |
| micromobility/access candidates | `10,325` |

The repository download helper `scripts/data/download-osm.sh` and the unpacked package helper `data/enrichment/source_packs/saferoute_moscow_data_pack/scripts/download_moscow_osm.sh` now download to a `.part` file, support resume, fail fast on sustained low speed, write a checksum after a complete download, and atomically move the completed file into place. They do not replace an existing working PBF with a partial download.

## Connected And Active

### OpenStreetMap / Geofabrik Way Tags

- Status: active
- Dataset version: `osm-moscow-oblast-tags-20260419`
- Source URL: `https://download.geofabrik.de/russia/central-fed-district.html`
- License: ODbL 1.0; attribution required
- Local source: `data/osm/moscow-oblast.osm.pbf`
- Source checksum: `sha256:939e71c748e20c75b020b05fbbddb10f0f627f54daf168210af72056669118da`
- Import command: `ACTIVATE_ENRICHMENT=true npm run db:enrichment-import:osm`
- Validation: `npm run db:enrichment-check && npm run db:enrichment-report`
- Join: direct OSM way ids from `public.moscow_network.osmid`

Active factors: `surface_type`, `surface_quality`, `sidewalk_presence`, `lighting_quality`, `slope_percent`.

### OpenStreetMap / Geofabrik Crossing Ways

- Status: active
- Dataset version: `osm-moscow-oblast-crossings-20260419`
- Source URL: `https://download.geofabrik.de/russia/central-fed-district.html`
- License: ODbL 1.0; attribution required
- Local source: `data/osm/moscow-oblast.osm.pbf`
- Source checksum: `sha256:939e71c748e20c75b020b05fbbddb10f0f627f54daf168210af72056669118da`
- Generated CSV checksum: `sha256:eb5adb84c83f1917d4e0b0ecb8db3ef70be164d00c0889ee9039b0f133ec3931`
- Import command: `npm run db:enrichment-import:crossings-osm`
- Validation: `17,526` matched crossing ways, `62,328` imported edge rows, ambiguous rate `0.0`, average confidence `0.909`
- Join: direct OSM way ids from `public.moscow_network.osmid`; point/node crossings are not guessed

Active factors: `crossing_count`, `controlled_crossing_count`, `uncontrolled_crossing_count`, `crossing_risk`.

## Evaluated But Not Activated

### OSM Kerb / Curb Features

- Status: pipeline-ready, inactive
- Source URL: `https://download.geofabrik.de/russia/central-fed-district.html`
- License: ODbL 1.0; attribution required
- Local source: `data/osm/moscow-oblast.osm.pbf`
- Source checksum: `sha256:939e71c748e20c75b020b05fbbddb10f0f627f54daf168210af72056669118da`
- Generated rejected CSV checksum: `sha256:86dd0aa235fae988ce88533036f5428a8cc391e7143bf647f162c555c07f1703`
- Extraction filters: `kerb=*`, `kerb:left/right`, `kerb:height`, `crossing:kerb`, `sidewalk:*:kerb`, `barrier=kerb`, `highway=kerb`, `sloped_curb`, `ramp:kerb`, `kerb:ramp`, plus supporting-only audit tags `tactile_paving`, `wheelchair`, and generic `ramp`.
- Supporting-only policy: `tactile_paving`, `wheelchair`, and generic `ramp` are counted in the audit but do not create curb risk without a curb/kerb/ramp-to-kerb signal.
- Source audit: `104,030` raw extracted features; `43,870` normalized real curb/kerb/ramp-to-kerb features (`35,110` lines, `8,760` points).
- Mapping attempted: direct OSM way id, nearest graph-node neighborhood within `3m`, crossing-assisted point mapping within `3m`, and strict line spatial join within `3m`.
- Validation result: `495` accepted source features and `1,540` candidate edge rows, but `29,854` ambiguous features and `0.9837` ambiguous rate. Required: at least `1,000` accepted features, at least `1,000` edge rows, and ambiguous rate `<= 0.15`.
- Distance/class result: median distance `0.0m`, p95 distance `2.753m`, plausible edge rate `1.0`, incompatible edge rate `0.0`.
- Decision: do not activate `curb_risk`, `curb_frequency`, or `curb_density_per_km`.
- Launch-safe wording: curb risk remains inactive because reliable edge-mapped curb data is not available yet.

### OSM Maxspeed/Lanes As Traffic

- Status: not activated as `traffic_intensity`
- Reason: graph already uses `maxspeed` and `lanes` as road-exposure attributes. They are not measured traffic intensity.

### Open-Meteo Weather

- Status: implemented as optional dynamic provider, disabled by default
- Source URL: `https://open-meteo.com/en/docs`
- License/terms: CC BY 4.0 API data; see `https://open-meteo.com/en/licence`
- Activation: `SAFEROUTE_WEATHER_ENABLED=true`, `SAFEROUTE_WEATHER_PROVIDER=open_meteo`
- Behavior: route-level weather risk is fetched at the route bbox centroid and cached. Provider failure produces no weather reason.

### Official Micromobility Zones

- Status: pipeline-ready, inactive
- Candidate official source: `https://transport.mos.ru/kicksharing/slow-zones`
- Source evaluation: the official Moscow Transport page confirms slow/prohibited SIM zones, but a reproducible licensed polygon/API export is not present in the repo and has not been verified.
- Rejected source for this layer: OSM access/bicycle tags and `queries/overpass_moscow_micromobility_candidates.ql`. They may be useful as a separate OSM access proxy, but they are not official scooter zone polygons.
- Import command, once a real source exists: `npm run db:enrichment-import:micromobility-zones`
- Validation/docs: `docs/MICROMOBILITY_ZONES.md`
- Decision: keep `micromobility_allowed`, `forbidden_zone`, `micromobility_slow_zone`, and `zone_speed_limit_kmh` inactive until a checksum-verified official/legal polygon source passes graph intersection validation.

### Traffic / Pedestrian / Telemetry Source Pack

- Status: evaluated as requirements and source leads only
- Local path: `data/enrichment/source_packs/saferoute_traffic_pedestrian_telemetry_data_pack/`
- Source inventory: `sources_traffic_pedestrian_telemetry.csv`
- Included docs: telemetry, measured traffic, and pedestrian-density requirements
- Production data decision: the pack contains no real telemetry observations, no measured traffic export, and no pedestrian-density export. It must not be imported as active production data.

| Layer | Candidate | License/terms | Status | Decision |
|---|---|---|---|---|
| `telemetry_confidence` | SafeRoute own `sidewalk_samples` / `sidewalk_cell_aggregates` | First-party data; privacy/consent required | Inactive | Current verified row counts are `0`, so `avg_telemetry_confidence` remains `null`. |
| `traffic_intensity` | Moscow Traffic Control Centre / ЦОДД, `https://gucodd.ru/` | Official/API agreement required if available | Official lead | Not active: no reproducible public edge-level dataset/API export is present. |
| `traffic_intensity` | xMap Russia Road Traffic Data | Commercial contract required | Commercial candidate | Not active without reviewed license terms and a source export file. |
| `pedestrian_density` | Moscow pedestrian/bicycle master planning project | Not an open dataset | Lead only | Not active: project page is not a downloadable licensed dataset. |
| `pedestrian_density` | SmartLoc pedestrian heatmaps Moscow | Commercial terms required | Commercial candidate | Not active without reviewed license terms and a source export file. |
| crash-risk future layer | Russian road accident / ДТП data | Source terms must be checked | Separate future candidate | Not measured traffic. Do not import into `traffic_intensity`. |
| `weather_sensitive_risk` | Open-Meteo | CC BY 4.0 API data | Implemented optional dynamic provider | Not part of this static measured source pack; enabled only by explicit weather env. |

Future import interfaces:

- `npm run db:traffic-import:measured`
- `npm run db:pedestrian-import:density`

Both are fail-closed. They require provider/owner, source URL/path, license/terms, checksum, dataset version, timestamp or time bucket, confidence, edge mapping, and explicit `ACTIVATE_ENRICHMENT=true`. Test fixtures, OSM road-class/maxspeed/lanes, POI/transit proxies, accident data, and commercial leads without licensed exports cannot be activated.

## Required Future Sources

| Factor | Required source |
|---|---|
| `curb_risk` / `curb_density_per_km` | Higher-confidence curb inventory, accessibility survey, or validated telemetry-derived edge layer |
| `traffic_intensity` | Traffic count, speed, or congestion source with license and edge/corridor mapping |
| `pedestrian_density` | Sensor/footfall/crowding source with coverage and privacy review |
| `micromobility_forbidden_zones` | Official maintained zone polygons with license/terms, checksum, and graph-intersection validation |
| `micromobility_slow_zones` | Official maintained zone polygons with speed limits, license/terms, checksum, and graph-intersection validation |
| `telemetry_confidence` | Real sidewalk telemetry samples or validated edge aggregation |
