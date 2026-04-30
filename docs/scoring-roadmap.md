# SafeRoute Scoring Roadmap

This roadmap lists scoring inputs that the product wants but the current `public.moscow_network` graph does not yet expose reliably. These items are not implemented in production behavior until real data exists.

## Current Implemented Data

First-stage scoring uses only current graph attributes:

- `safety_weight`
- `highway`
- `access`
- `width`
- `est_width`
- `maxspeed`
- `lanes`
- `length`

Active OSM enrichment currently also provides surface, surface quality, sidewalk presence, lighting tags, sparse slope values, and direct OSM crossing way counts. See `docs/ENRICHMENT_DATA.md`.

These support:

- hard avoid for explicit forbidden access, steps, motorway/trunk-like edges for pedestrian and bike routes
- penalties for narrow edges, track-like edges, high maxspeed, and many lanes
- positive reasons for wide edges, low-speed streets, cycleway-like bike edges, and footway/pedestrian walking edges

## Scoring Data Dictionary

These are the canonical SafeRoute factor names. Runtime scoring may use a factor only when the graph or overlay has real data for it. Missing factors must remain absent from `properties.score.reasons[]`.

| Factor | Accepted values or unit | Source type | Scoring intent |
| --- | --- | --- | --- |
| `surface_type` | `asphalt`, `paving_stones`, `cobblestone`, `gravel`, `dirt` | graph column or joined surface layer | Penalize cobblestone, gravel, dirt; reward asphalt only when real data exists. |
| `surface_quality` | `smooth`, `moderate`, `broken` | graph column, survey layer, or telemetry-derived layer | Penalize broken surface; reward smooth surface. |
| `sidewalk_presence` | explicit true/false or side-specific presence | graph column or joined sidewalk inventory | Penalize missing sidewalks for walk/bike/accessibility. Hard avoid only after coverage is validated. |
| `sidewalk_width_m` | meters | graph column or joined sidewalk inventory | Penalize narrow sidewalks, strongest in accessible mode; reward wide sidewalks. |
| `curb_frequency` | count per edge or normalized route segment | curb/accessibility observations | Penalize high curb frequency, strongest in accessible mode. |
| `curb_risk` | normalized `0..1` | curb/accessibility observations | Penalize high curb risk. |
| `crossing_count` | count | crossing/intersection layer | Penalize many crossings, especially in safest and accessible modes. |
| `lighting_quality` | `good`, `moderate`, `poor`, `unlit` | lighting coverage or night-safety layer | Penalize poor/unlit edges; reward good lighting. |
| `slope_percent` / `incline` | percent grade | elevation-derived graph layer | Penalize steep slope, strongest in accessible mode. |
| `traffic_intensity` | normalized `0..1` | traffic count, speed, or congestion layer | Penalize high traffic; reward low traffic. |
| `pedestrian_density` | normalized `0..1` | crowding/city sensor/derived layer | Penalize high pedestrian density where it creates accessibility or micromobility conflict. |
| `micromobility_allowed` | explicit true/false | regulation/zone layer | Hard avoid explicit forbidden micromobility edges for bike/micromobility contexts. |
| `forbidden_zone` | explicit true/false | regulation/zone layer | Hard avoid explicit forbidden zones. |
| `weather_sensitive_risk` | normalized `0..1` | dynamic provider or graph/overlay risk layer | Penalize routes or edges known to become risky in rain/snow/ice only when a real provider/overlay is enabled. |
| `telemetry_confidence` | normalized `0..1` | telemetry overlay or validated graph enrichment | Reward high-confidence telemetry; do not penalize missing telemetry. |

Implementation supports these as optional graph columns when present. Dynamic overlays, such as weather or H3 telemetry along a route, must stay separate from static graph columns until there is real data and tests.

## Required Data Before Future Scoring

TODO: Missing sidewalk detection

- Required source: reliable sidewalk presence per edge or side-of-street.
- Required graph column or joined table: `sidewalk_presence`, `sidewalk_left`, `sidewalk_right`, or equivalent.
- Production behavior: hard avoid only after coverage and false-positive rate are understood.

TODO: Surface quality

- Required source: real surface tags, survey data, telemetry inference, or maintained city data.
- Required graph column or joined table: `surface_type`, `surface`, `surface_quality`, or normalized equivalent.
- Production behavior: high penalty for cobblestone, gravel, broken pavement; positive reason for smooth asphalt.

TODO: Curb density and accessibility barriers

- Required source: curb observations or accessibility map data.
- Required graph column or joined table: `curb_density`, `curb_height_cm`, `barrier_score`, or equivalent.
- Production behavior: strong accessible-mode penalty after validation.

DONE/PARTIAL: Crossings

- Current source: direct OSM crossing ways mapped through `public.moscow_network.osmid`.
- Active factors: `crossing_count`, `controlled_crossing_count`, `uncontrolled_crossing_count`, `crossing_risk`.
- Remaining gap: node-only crossing features are not guessed; future work may add audited point aggregation if ambiguity can be controlled.

TODO: Lighting

- Required source: real lighting coverage or night-safety layer.
- Required graph column or joined table: `lighting_score` or equivalent.
- Production behavior: medium penalty for poor lighting, mode-dependent and time-of-day aware.

TODO: Slope

- Required source: elevation-derived grade per edge.
- Required graph column or joined table: `slope_percent`, `uphill_grade`, or equivalent.
- Production behavior: medium penalty for steep slope, stronger in accessible mode.

TODO: Dedicated bike-lane quality

- Required source: lane type and protection level, not only `highway=cycleway`.
- Required graph column or joined table: `bike_lane_type`, `bike_lane_protected`, or equivalent.
- Production behavior: positive weight for dedicated or protected bike lanes.

TODO: Traffic intensity

- Required source: traffic count, speed, or congestion layer.
- Required graph column or joined table: `traffic_score`, `vehicle_volume`, or equivalent.
- Production behavior: penalty for high traffic and positive reason for low traffic.

TODO: Pedestrian density

- Required source: real pedestrian counts, privacy-safe crowding sensors, or maintained city data.
- Required graph column or joined table: `pedestrian_density` normalized to `0..1`.
- Production behavior: penalty for high density where it creates accessibility or micromobility conflict.

TODO: Micromobility and forbidden zones

- Required source: official regulation polygons or maintained operational zones.
- Required graph column or joined table: `micromobility_allowed`, `forbidden_zone`, or joined zone overlay.
- Production behavior: hard avoid only for explicit forbidden values; unknown values must not be treated as forbidden.

TODO: Weather-sensitive risk

- Required source: maintained weather-risk overlay or live weather integration with clear coverage and freshness rules.
- Required graph column or joined table: `weather_sensitive_risk` normalized to `0..1`, or a tested dynamic overlay.
- Production behavior: penalty for edges known to become risky during relevant weather. Do not infer live weather risk without a real source.

TODO: Telemetry confidence along routes

- Required source: real `sidewalk_cell_aggregates` samples intersecting route samples or validated graph enrichment.
- Required graph column or overlay: `telemetry_confidence` normalized to `0..1`.
- Production behavior: positive reason for high-confidence telemetry; missing telemetry should not lower score by itself.

## Implementation Rules

- Do not create fake graph data to satisfy a scoring factor.
- Do not infer a future factor from unrelated fields unless the inference is explicitly documented and tested.
- Add each new factor with data coverage checks, scoring tests, route smoke verification, and docs.
