# Telemetry Confidence

Telemetry confidence is implemented as a route-level overlay from real sidewalk telemetry H3 cells. It remains inactive until SafeRoute has real observations in `sidewalk_samples` / `sidewalk_cell_aggregates`.

## Current Status

- `sidewalk_samples`: `0` active rows in the verified local stack
- `sidewalk_cell_aggregates`: `0` active rows in the verified local stack
- `avg_telemetry_confidence`: must remain `null`
- Score reason `telemetry_confidence`: must not appear
- `score.data_sources.telemetry`: absent

The package `data/enrichment/source_packs/saferoute_traffic_pedestrian_telemetry_data_pack/` has been inspected as a requirements/source-evaluation pack only. It contains telemetry requirements and a SQL template, but no real telemetry observations. The SQL template must not be run as a production seed.

## Runtime Behavior

The route scorer samples route geometry into H3 cells using the configured telemetry resolution. It then reads `sidewalk_cell_aggregates` and, where present, `sidewalk_samples` for raw consistency. If no route cells have real observations, or route-cell coverage is too low, the service returns no telemetry source and no factor value.

When real rows exist, confidence combines:

- observation count, log-scaled with full count score around 20 samples per cell;
- recency from `last_seen_at` with exponential decay;
- agreement/consistency from raw `quality_score` variance when raw samples exist;
- sensor quality from existing telemetry `confidence`, which is derived from GPS accuracy;
- route coverage across sampled H3 cells.

The output is bounded `0..1` and exposed only as:

- `score.factors.avg_telemetry_confidence`
- optional positive reason `telemetry_confidence` when confidence is high enough
- `score.data_sources.telemetry` metadata: sample count, cell count, coverage, average confidence, and latest observation time

Telemetry confidence is not surface quality, curb quality, traffic, or accessibility truth. It is only confidence that real telemetry covers the sampled route cells.

## Activation Requirements

Telemetry confidence may be active only after real telemetry exists and passes validation:

- source and collection method are documented;
- privacy review is complete;
- observation count is sufficient for the claimed coverage;
- recency is tracked;
- consistency/agreement across observations is measured;
- source quality is represented where available;
- mapping to audited H3 route cells or `public.moscow_network.id` is documented;
- validation report includes row count, coverage, confidence distribution, and null rates.

The source package restates the required observation contract:

- `observation_id`
- `observed_at`
- `source_type`
- latitude/longitude, `h3_cell`, or `edge_id`
- `quality_score` or the observed sidewalk factor
- source confidence from a sensor/model/user source
- optional pseudonymized device/session identifier
- documented privacy and consent policy

## Operator Commands

```bash
npm run db:telemetry-check
npm run db:telemetry-report
```

`db:telemetry-report` is read-only. It reports raw sample count, aggregate cell count, source distribution, confidence distribution, and observation recency.

## No-Fake Rule

Test fixtures may exercise telemetry-confidence scoring under `tests/`, but fixtures must never be imported as active production data. The model must not infer confidence from the existence of an import file, enrichment metadata, graph dump, OSM tags, or route geometry alone. If real telemetry rows are absent, UI/API must communicate telemetry confidence as unavailable.

Generated H3 cells, import confidence, source metadata, OSM tags, measured traffic files, and pedestrian-density files are not telemetry confidence. With the current verified row counts of zero, telemetry confidence remains inactive / pipeline-ready.
