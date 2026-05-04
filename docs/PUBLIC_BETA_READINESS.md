# Public Beta Readiness

This checklist is the practical release gate for SafeRoute public beta. It is not a safety-grade launch checklist.

## Ready For Public Beta

- Real Moscow routing is available through the self-hosted Valhalla/PostGIS/pgRouting stack.
- OSM-derived enrichment is active for surface, surface quality, sidewalk presence, lighting tags, sparse slope, and OSM crossings.
- Missing advanced layers are fail-closed: curb, official SIM zones, measured traffic, pedestrian density, and telemetry confidence remain inactive unless validated real datasets exist.
- Weather risk is optional and dynamic; it is disabled unless `SAFEROUTE_WEATHER_ENABLED=true`.
- Route UI says scores are based on available data and are not guarantees.
- Route cards hide technical source labels and focus on choice, time, distance, score, and one reason.
- The public planner exposes only walking and wheels/micromobility profiles. Car routing remains an API capability for diagnostics/smoke coverage, but it is not presented as a public beta user mode because the safety graph is focused on sidewalks and micromobility.
- Local feedback is not telemetry and does not affect routing.
- `/api/health` includes runtime readiness metadata so fallback cannot be mistaken for self-hosted readiness.
- Route operational metrics are grouped by profile/mode/outcome and do not store route coordinates.

## Required Verification

```bash
npm run build
npm run lint
npm run check:release-readiness
npm run typecheck:backend
npm run test:backend
npm run check:backend
npm run check:full
npm run db:enrichment-check
npm run db:enrichment-report
npm run db:telemetry-report
npm run smoke:api
npm run smoke:self-hosted
npm run route:corpus-check
npm run perf:route-smoke
APP_URL=http://127.0.0.1:5173 npm run test:e2e
```

## Release Blockers

- Any fake or synthetic safety factor in production data.
- Any UI claim that an inactive layer is active.
- Hidden telemetry writes.
- Map attribution hidden or unreadable.
- Production-like mode silently using public Photon/Valhalla fallback.
- Trust-copy check failure.

## Launch-Safe Wording

Use: "SafeRoute is ready for public beta with real OSM-derived route enrichment and clear data limits."

Do not use: "SafeRoute guarantees the safest route" or "full public safety launch."
