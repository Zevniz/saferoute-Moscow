# SafeRoute Beta Safety Limits

SafeRoute is ready for public beta, not for full safety-grade launch. The product helps compare routes by available data, but it cannot guarantee real-world safety conditions.

## What The Beta Can Claim

- Routes are calculated from real routing services and the local Moscow graph.
- Active OSM-derived enrichment can affect scoring.
- Active crossing data can affect scoring.
- Optional weather risk can affect scoring only when enabled and returned by Open-Meteo.
- Missing advanced layers are not faked.

## What The Beta Cannot Claim

- It cannot know every curb, ramp, or barrier.
- It cannot claim official micromobility zone coverage without validated official polygons.
- It cannot claim measured traffic or pedestrian density without licensed measured data.
- It cannot claim telemetry confidence while `sidewalk_samples` and `sidewalk_cell_aggregates` are empty.
- It cannot guarantee a route is safe at the moment of travel.

## UI Copy Rules

The primary UI should say:

- “Оценка маршрута.”
- “По доступным данным.”
- “Не гарантия безопасности.”
- “Часть факторов пока неизвестна.”

The primary UI should avoid:

- legalistic walls of text;
- alarmist warnings for inactive layers;
- technical source noise in route cards;
- any statement that inactive factors are active.

## Current Inactive Layers

- curb risk / curb density: rejected for activation after ambiguous mapping.
- official micromobility zones: pipeline-ready, no legal reproducible polygon source active.
- measured traffic: pipeline-ready, no licensed measured export active.
- pedestrian density: pipeline-ready, no licensed measured export active.
- telemetry confidence: pipeline-ready, real telemetry row count is zero.

These limits are product features, not footnotes: they protect user trust and prevent false precision.
