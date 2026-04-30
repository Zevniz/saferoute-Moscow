# Routing And Safety

## Route Assembly

SafeRoute returns only real candidate routes:

1. FastAPI asks Valhalla for ordinary `walk`, `bike`, or `car` route candidates with maneuver narratives.
2. FastAPI generates a mode-aware safety route from `moscow_network` using pgRouting and the safety-weighted graph.
3. The safety route is passed through Valhalla `trace_route` to get real turn-by-turn instructions where the Valhalla service accepts the trace.
4. Every route is enriched with a safety score by sampling the route geometry against nearest `moscow_network` edges.
5. Routes are labeled deterministically as `safe`, `balanced`, and `fast` when enough unique real candidates exist.

If an engine returns fewer viable candidates, the API returns fewer candidates. It does not synthesize fake alternates or fake navigation maneuvers.

## Route Modes

`GET /api/route` accepts an optional `mode` query parameter:

- `safest`: default. Safety penalties dominate distance.
- `balanced`: safety remains first-class, but distance/time has more influence.
- `fastest`: keeps hard avoids, but minimizes travel time more aggressively.
- `accessible`: strongest penalties for narrow or unsuitable walking edges; intended primarily for pedestrian routing.

The public route variants remain `safe`, `balanced`, and `fast`. `mode` changes how the safety graph is scored; it does not create fake alternatives or placeholder instructions.

Mode differences are limited by the real graph attributes sampled along each route. If two modes sample the same route geometry and the available edges only expose `safety_weight`, their score explanations may differ only slightly or not at all. That is expected for the first-stage scoring model and is preferable to inventing missing sidewalk, surface, lighting, slope, curb, crossing, or traffic facts.

The scoring architecture lives in `app/services/scoring.py`:

- `RoutingMode`: `safest`, `fastest`, `balanced`, `accessible`.
- `SCORING_CONFIGS`: mode-specific weights for current real graph attributes.
- `RouteAttributeSummary`: sampled attributes from nearest real `moscow_network` edges.
- `calculate_route_score`: pure score calculation plus explanation reasons.

Routes include an additive `properties.score` object with:

- `mode`
- `total`
- `safety_index`
- `factors`
- `reasons[]`
- `data_sources.enrichment`

Existing clients can continue using `properties.safety_index`.

In the public beta, `data_sources.enrichment.active` is `true` for `osm-moscow-oblast-tags-20260419` and `osm-moscow-oblast-crossings-20260419`. Active factors include `lighting_quality`, `sidewalk_presence`, `slope_percent`, `surface_quality`, `surface_type`, `crossing_count`, `controlled_crossing_count`, `uncontrolled_crossing_count`, and `crossing_risk`. Advanced factors such as curb risk, measured traffic intensity, pedestrian density, micromobility zones, default weather-sensitive risk, and telemetry confidence remain `null` or absent unless a real active dataset or provider supplies them.

The current graph has real columns for:

- `highway`
- `access`
- `width`
- `est_width`
- `maxspeed`
- `lanes`
- `safety_weight`

Those columns support the current production scoring:

- Hard avoid: explicit forbidden access, steps for pedestrian/bike/accessibility routing, motorway/trunk-like edges for pedestrian and bike routing.
- High penalty: narrow edges, high-speed or many-lane roads, track-like edges, high `safety_weight`.
- Positive weight: wider edges, low-speed roads, bike-oriented `cycleway` edges for bike routing, footway/pedestrian edges for walking.

The product scoring model also calls for factors such as missing sidewalks, cobblestone/gravel/broken pavement, curb density, crossings, lighting, slope, dedicated bike lanes, smooth asphalt, and traffic. The public beta currently activates only the OSM-derived factors documented in [Enrichment Data](ENRICHMENT_DATA.md). Do not fake missing factors. Add them only when the real graph has reliable columns or joined datasets for those facts. See [Scoring Roadmap](scoring-roadmap.md).

The scoring code is prepared to read those expanded factors as optional real columns when they exist, including surface, sidewalk, curb, crossing, lighting, slope, traffic, pedestrian density, micromobility zone, weather-risk, and telemetry-confidence fields. If the columns or overlays are absent, the factors remain `null` or absent from explanations and do not affect route selection or score.

## Profiles

- `walk`: excludes motorway/trunk-like edges from the safety graph.
- `bike`: excludes steps and penalizes primary/secondary roads.
- `car`: excludes footway/path/steps/pedestrian/track/cycleway-like edges and falls back to a softer filter when the local graph is disconnected.

## Safety Index And Score

The API samples a route line and finds the nearest `moscow_network` edge for each sample. The base safety index is anchored in average `safety_weight`:

```text
safety_index = clamp(100 - ((avg_weight - 1) / 4) * 100, 0, 100)
```

The first-stage score then adjusts that base with only available route attributes:

- width or estimated width
- maxspeed
- lanes
- highway class fractions

Higher is safer. This keeps the score stable while still responding to the custom safety graph and giving clients explainable reasons.

In the verified local self-hosted graph, `safety_weight` is present for all edges, while optional attributes are sparse: `width`, `est_width`, `maxspeed`, `lanes`, and `access` are available only on subsets of `moscow_network`. Routes may therefore have identical geometry across modes, especially when Valhalla and pgRouting do not find distinct viable alternatives from the available graph. The API should surface that honestly through `properties.score.reasons[]` rather than adding synthetic reasons.

## Instructions

Frontend navigation renders `properties.instructions[]` from the route payload. It does not generate heuristic turn text. Instruction fields:

- `index`
- `text`
- `distance_m`
- `time_s`
- `begin_shape_index`
- `end_shape_index`
- `type`
- `street_names`
- `lanes`

## Data Requirements

The DB must contain `public.moscow_network` with at least:

- `id`
- `u`
- `v`
- `highway`
- `length`
- `safety_weight`
- `geometry`

`/api/health` marks Postgres as unhealthy if `moscow_network` is missing.

## Production Graph Preparation

Run `scripts/prepare-production-db.sql` after loading `moscow_network`. It removes duplicate indexes, adds profile-specific cost columns, endpoint coordinate columns for A*, and creates `moscow_network_nodes` for faster nearest-node lookup.

Runtime behavior:

- Prefer `pgr_aStar` when `source_x/source_y/target_x/target_y` are present and `ROUTE_GRAPH_ALGORITHM=astar`.
- Fall back to Dijkstra only after a technical A* failure, with a structured log event.
- Include `ROUTE_DATA_VERSION` in the route cache key so responses do not survive a graph/tile refresh.
- Cache route responses with TTL + LRU eviction; metrics expose hits, misses, expirations, variants, and failures.
