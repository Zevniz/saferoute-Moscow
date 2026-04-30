# Full Safety Launch Roadmap

SafeRoute public beta has real OSM-derived enrichment, but it is not a full public safety launch for every desired layer. Full safety launch claims require more real, legally usable, edge-mapped datasets.

## P0 Before Full Safety Claims

| Dataset | Required proof before activation |
|---|---|
| Curb risk / curb density | Real curb inventory, accessibility survey, or telemetry-derived edge layer with confidence and validation. The OSM curb pipeline is implemented but remains inactive: the expanded hybrid audit accepted only `495` source features and had `98.37%` ambiguity. |
| Measured traffic intensity | Traffic count, speed, or congestion source with license, version, and edge/corridor mapping. |
| Micromobility forbidden/slow zones | Official maintained zone polygons with update cadence and spatial join validation. |
| Telemetry confidence | Real sidewalk telemetry samples or validated edge aggregation; no confidence from import metadata alone. |

## P1 After P0

| Dataset | Required proof before activation |
|---|---|
| Pedestrian density | Sensor, footfall, or crowding source with privacy review and coverage report. |
| Weather-sensitive risk | Optional Open-Meteo integration exists, but production launch must explicitly enable it and accept/cache provider terms. Static edge weather risk still requires a maintained risk overlay. |

## Import Requirements

Every future dataset must include:

- legal source and license or terms;
- source URL or documented acquisition process;
- source checksum;
- dataset version and import timestamp;
- edge mapping to `public.moscow_network.id`, or an audited geometry join with distance thresholds;
- validation report with row count, coverage, unmatched count, ambiguous matches, and null rates;
- confidence field in the `0..1` range;
- activation flag that stays false until validation passes.

## No-Fake-Data Policy

- Do not infer missing curb, crossing, traffic, pedestrian, micromobility, weather, or telemetry-confidence values from unrelated fields.
- Do not treat OSM `maxspeed` or `lanes` as measured `traffic_intensity`.
- Do not treat sparse OSM point tags as per-edge curb/crossing data without a tested aggregation pipeline.
- Direct OSM crossing ways are active; node-only crossings are not guessed.
- Do not activate sample/test fixtures in production.
- Test fixtures may exist only under `tests/` and must be clearly test-only.

## Scoring And UI Policy

Scoring may use a factor only when a real active dataset exposes that factor. Missing factors must remain `null` or absent from API score factors, and their reasons must not appear in the UI.

Public copy must continue to say public beta until all P0 datasets needed for full safety claims are active, validated, and verified through route corpus/browser QA.
