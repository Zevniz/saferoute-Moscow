# Public Launch Readiness

## Status

SafeRoute is ready for public beta / self-hosted MVP with active OSM-derived enrichment. It is not yet a full public safety launch for every desired factor.

## Ready

- Real routing through Valhalla/PostGIS/pgRouting.
- Published graph artifact and verified fresh restore.
- OSM-derived enrichment active for surface, sidewalk presence, lighting, sparse slope, and direct OSM crossing ways.
- Additive multi-dataset enrichment is active: the OSM way-tag dataset and OSM crossings dataset can both contribute to scoring.
- OSM/CARTO attribution is visible in the map UI.
- Production security controls are implemented and configurable.
- Browser/e2e/smoke/route corpus checks pass in local self-hosted verification.
- Product UI is route-first for public beta: route cards show user-facing time, distance, score, and one reason; technical source details live in the score disclosure and "О сервисе".
- Navigation mode keeps map controls usable, shows the next maneuver and remaining trip summary first, and keeps the full maneuver list secondary.
- Route details separate safety score from data confidence, compare the selected route with alternatives, and show a pre-trip "what to expect" timeline derived only from returned API reasons.
- Route details explicitly state that the score is based on available data and is not a safety guarantee.
- Local route feedback is UI-only in this build. It stays in the current interface session, is not sent to the server, does not affect routes, and must not be counted as telemetry.

## Conditional

- Production deployment must set API keys, rate limits, and deep-health protection in the target secret/config manager.
- Distribution/release notes must keep OSM ODbL attribution and derived-data obligations explicit.
- Figma source verification remains a design-governance blocker until the MCP-authenticated account can access file `hZn31Z6alrXnUoxyyKCrmq`. Runtime readiness is based on code, browser QA, and e2e until then.

## Not Yet Ready For Full Safety Claims

Do not claim SafeRoute accounts for these until real active datasets are imported:

- curb risk/density: OSM curb pipeline exists, but validation did not meet activation threshold (`495` accepted features, `98.37%` ambiguity).
- measured traffic intensity: pipeline-ready but inactive. The evaluated source pack provides requirements and leads only; no licensed measured traffic export is present.
- pedestrian density: pipeline-ready but inactive. The evaluated source pack provides requirements and leads only; no licensed measured pedestrian-density export is present.
- micromobility forbidden/slow zones: import pipeline exists, but no legally usable, reproducible official Moscow/Moscow Oblast zone polygon source is active.
- weather-sensitive risk in default runtime. Optional Open-Meteo integration is implemented behind `SAFEROUTE_WEATHER_ENABLED=true`.
- telemetry confidence: route-level H3 overlay is implemented, but the verified stack has `0` `sidewalk_samples` and `0` `sidewalk_cell_aggregates`, so it remains inactive.

Launch-safe wording:

> Measured traffic, pedestrian density, and telemetry confidence are pipeline-ready but inactive until real licensed observations/imports are available.

## Verification Commands

```bash
npm run db:enrichment-check
npm run db:enrichment-report
npm run db:telemetry-check
npm run db:telemetry-report
npm run build
npm run check:backend
npm run check:full
npm run smoke:api
npm run smoke:self-hosted
npm run route:corpus-check
npm run perf:route-smoke
APP_URL=http://127.0.0.1:5173 npm run test:e2e
```

Product strategy and UX audit:

- `docs/PRODUCT_STRATEGY.md`
- `docs/UX_REDESIGN_AUDIT.md`
