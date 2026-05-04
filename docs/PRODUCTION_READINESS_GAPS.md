# Production Readiness Gaps

SafeRoute is ready for a careful public beta, but it is not production-grade at city scale and not a safety-grade launch.

## Ready Now

- Self-hosted FastAPI, PostGIS/pgRouting, Photon, Valhalla, and Vite preview stack.
- Active real OSM-derived enrichment for surface, sidewalk, lighting, sparse slope, and crossings.
- Fail-closed inactive advanced layers.
- Health, metrics, smoke tests, route corpus, perf smoke, and trust-copy checks.
- Route scoring and explainability based on returned route data and active factors only.

## Public Beta Gaps

- Operational alerting is manual; metrics exist but no external monitor is configured.
- Route cache is in-process and per-container.
- Graph/import refresh cadence is documented but not automated.
- Auth/rate-limit controls are configurable but not yet enforced by default for every deployment shape.
- No production incident dashboard or runbook automation.
- Car routing is not exposed in the public planner. Before it can become user-facing, the graph needs a dedicated car-road validation report proving that no sidewalk/footway/path edges are used.

## Production-Grade Blockers

- Managed deployment target, secrets manager, backups, restore drills, and external monitoring.
- Load testing with representative route/search traffic.
- Formal data freshness schedule and import rollback process.
- Rate limiting and API-key policy enabled for public endpoints where required.
- CI gate that runs the full release checklist in a production-like environment.

## Safety-Grade Blockers

- No verified curb risk/density layer.
- No official licensed micromobility forbidden/slow-zone polygon source.
- No licensed measured traffic export.
- No licensed measured pedestrian-density export.
- No real telemetry rows in the verified stack.
- No external safety validation, legal review, or audited incident process.

Until these blockers are resolved, SafeRoute must be described as a public beta route decision aid, not a certified safety product.
