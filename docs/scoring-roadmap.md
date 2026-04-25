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

These support:

- hard avoid for explicit forbidden access, steps, motorway/trunk-like edges for pedestrian and bike routes
- penalties for narrow edges, track-like edges, high maxspeed, and many lanes
- positive reasons for wide edges, low-speed streets, cycleway-like bike edges, and footway/pedestrian walking edges

## Required Data Before Future Scoring

TODO: Missing sidewalk detection

- Required source: reliable sidewalk presence per edge or side-of-street.
- Required graph column or joined table: `sidewalk_presence`, `sidewalk_left`, `sidewalk_right`, or equivalent.
- Production behavior: hard avoid only after coverage and false-positive rate are understood.

TODO: Surface quality

- Required source: real surface tags, survey data, telemetry inference, or maintained city data.
- Required graph column or joined table: `surface`, `surface_quality`, or normalized equivalent.
- Production behavior: high penalty for cobblestone, gravel, broken pavement; positive reason for smooth asphalt.

TODO: Curb density and accessibility barriers

- Required source: curb observations or accessibility map data.
- Required graph column or joined table: `curb_density`, `curb_height_cm`, `barrier_score`, or equivalent.
- Production behavior: strong accessible-mode penalty after validation.

TODO: Crossings

- Required source: intersection/crossing count per edge or route segment.
- Required graph column or joined table: `crossing_count`, `uncontrolled_crossing_count`, or equivalent.
- Production behavior: medium penalty for many crossings, especially in accessible and safest modes.

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

## Implementation Rules

- Do not create fake graph data to satisfy a scoring factor.
- Do not infer a future factor from unrelated fields unless the inference is explicitly documented and tested.
- Add each new factor with data coverage checks, scoring tests, route smoke verification, and docs.
