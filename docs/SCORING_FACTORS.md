# Scoring Factors

SafeRoute scoring uses only real present factors. Missing data produces no penalty, no bonus, and no reason.

## Active Real Enrichment Factors

| Factor | Source | Scoring behavior |
|---|---|---|
| `surface_type` | OSM `surface` via direct way ID join | Cobblestone/gravel/dirt penalize; asphalt can create a positive surface reason. |
| `surface_quality` | OSM `smoothness` via direct way ID join | Broken penalizes; smooth can create a positive surface reason. |
| `sidewalk_presence` | OSM sidewalk tags via direct way ID join | Explicit missing sidewalk penalizes walk/bike/accessibility. |
| `lighting_quality` | OSM `lit` via direct way ID join | Poor/unlit penalizes; good lighting can add a small positive reason. This is tag-derived, not measured illumination. |
| `slope_percent` | Numeric OSM `incline` via direct way ID join | Steep slopes penalize, strongest in accessible mode. |
| `crossing_count` | OSM crossing ways via direct way ID join | Many direct crossing ways add a medium penalty. |
| `controlled_crossing_count` | OSM crossing/signal tags where present | Used as explanation/supporting factor; controlled crossings reduce `crossing_risk`. |
| `uncontrolled_crossing_count` | OSM crossing tags where uncontrolled or unknown | Used as explanation/supporting factor; uncontrolled/unknown crossings raise `crossing_risk`. |
| `crossing_risk` | Tag-derived OSM crossing risk | Higher values can create a crossing penalty. |

## Existing Graph Factors

These are not enrichment rows but already exist in `public.moscow_network`:

- `safety_weight`
- `highway`
- `width` / `est_width`
- `maxspeed`
- `lanes`
- `access`

`maxspeed` and `lanes` are graph road-exposure attributes. They are not labeled as measured `traffic_intensity`.

## Optional Dynamic Factor

| Factor | Source | Default | Behavior |
|---|---|---|---|
| `weather_sensitive_risk` | Open-Meteo current weather at the route bbox centroid, when enabled | Disabled | Adds a proportional route-level weather reason only when `SAFEROUTE_WEATHER_ENABLED=true` and the provider returns real data with positive risk. Provider failure degrades silently with no fake reason. |

## Missing Or Blocked Factors

| Factor | Status |
|---|---|
| `curb_risk`, `curb_frequency`, `curb_density_per_km` | Pipeline exists but inactive. The expanded OSM curb audit produced only `495` accepted source features and `1,540` candidate edge rows, with `98.37%` ambiguity, so curb factors do not affect scoring. |
| `traffic_intensity` | Pipeline-ready but inactive. `npm run db:traffic-import:measured` requires a real licensed measured source with checksum, timestamp/time bucket, raw counts/speeds/congestion, edge mapping, and explicit activation. |
| `pedestrian_density` | Pipeline-ready but inactive. `npm run db:pedestrian-import:density` requires a real licensed measured count/flow/density source with privacy review, checksum, timestamp/time bucket, edge mapping, and explicit activation. |
| `micromobility_allowed`, `forbidden_zone`, `micromobility_slow_zone`, `zone_speed_limit_kmh` | Pipeline-ready but inactive. Import requires official/legal Moscow zone polygons with checksum, license/terms, explicit `zone_type`, confidence, valid EPSG:4326 geometry, and graph-intersection validation. |
| `telemetry_confidence` | Route-level H3 telemetry-confidence overlay is implemented, but inactive in the verified stack because `sidewalk_samples` and `sidewalk_cell_aggregates` have `0` rows. |

## Curb Fail-Closed Rule

The current OSM curb/kerb candidate extraction is real, but it is not reliable enough to score routes. The importer writes audit metadata and a rejected CSV under ignored `data/enrichment/osm/` paths, then refuses activation unless validation passes. Missing curb data is never interpreted as curb-free or accessible.

Launch-safe wording:

> Curb risk remains inactive because reliable edge-mapped curb data is not available yet.

## API Contract

Route score reasons are machine-readable:

- `code`
- `impact`
- `message`
- `value`
- `weight`

The route score includes `data_sources.enrichment`. With multiple active datasets, the response preserves the old top-level dataset fields and adds `datasets[]` plus `dataset_versions[]`.

Public beta route responses may expose:

```json
{
  "data_sources": {
    "enrichment": {
      "active": true,
      "active_factors": [
        "crossing_count",
        "crossing_risk",
        "lighting_quality",
        "sidewalk_presence",
        "slope_percent",
        "surface_quality",
        "surface_type"
      ],
      "dataset_versions": [
        "osm-moscow-oblast-crossings-20260419",
        "osm-moscow-oblast-tags-20260419"
      ]
    }
  }
}
```

Inactive factors such as `avg_curb_risk`, `avg_traffic_intensity`, `avg_pedestrian_density`, and `avg_telemetry_confidence` must remain `null` or absent until real active datasets or telemetry observations provide them. Their score reasons must not appear.

## UI Behavior

The public route cards intentionally hide technical source labels such as Valhalla or raw OSM dataset names. They show only the route name, time, distance, score, and one top reason. Detailed active source badges and inactive-layer notes are available inside "Почему такая оценка" and "О сервисе" so the main planner stays useful without implying unavailable data is active.

The frontend also computes a display-only data confidence value from existing score metadata, active enrichment factors, and active provider metadata. It is not a new safety factor and does not change backend scoring. It exists to help users understand how much verified data supports the visible explanation.

The UI separates route score, data confidence, route priority, and unknown risk. Route score is a comparative value, not a guarantee of safety. Data confidence describes support from available active metadata, not certainty about real-world conditions.

The "Что по пути" timeline is derived from returned score reasons and maneuver text. It must not invent segment-level facts that the API did not provide. The “Что мы знаем / Что мы не знаем” block is built from the same route payload and the known inactive-layer list.

## Telemetry Confidence Rule

`avg_telemetry_confidence` is computed only from real `sidewalk_cell_aggregates` and `sidewalk_samples` intersecting route-sampled H3 cells. It combines observation count, recency, raw-sample agreement where available, sensor/GPS confidence, and route-cell coverage.

Telemetry confidence may add only a small positive confidence reason. It must never create surface, curb, traffic, pedestrian-density, weather, or accessibility claims.

## Measured Traffic And Pedestrian Density Rules

`avg_traffic_intensity` may come only from real measured traffic counts, speeds, or congestion data that is licensed, timestamped, checksum-verified, confidence-scored, and mapped to `public.moscow_network.id`. OSM `highway`, `maxspeed`, and `lanes` are not measured traffic and must stay under separate road-exposure wording.

`avg_pedestrian_density` may come only from measured or licensed estimated pedestrian counts, flows, densities, or heatmaps with privacy/licensing review and audited edge mapping. POIs, transit stops, stations, and land-use density are proxies and must not be activated as measured pedestrian density.

The traffic/pedestrian source pack is requirements-only; it contains no active source export. Until a real licensed file is imported, these factors remain `null` and their reasons must not appear.

## Micromobility Zone Fail-Closed Rule

The scoring code can consume active official zone rows, but the current public beta has no active official micromobility zone dataset. The OSM micromobility/access candidate query is not treated as city/operator scooter zones.

If a future official source passes `docs/MICROMOBILITY_ZONES.md` validation:

- `forbidden` zones may set `micromobility_allowed=false` and `forbidden_zone=true`;
- `slow` zones may set `micromobility_slow_zone=true` and `zone_speed_limit_kmh`;
- route reasons `micromobility_forbidden`, `forbidden_zone`, and `micromobility_slow_zone` may appear only for active real rows.

Launch-safe wording while inactive:

> Official micromobility forbidden/slow zones remain inactive because no legally usable, reproducible edge-mappable Moscow zone dataset is available yet.
