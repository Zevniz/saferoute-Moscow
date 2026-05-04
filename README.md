# SafeRoute

SafeRoute is a public beta safety-first navigator for Moscow micromobility. It uses real Valhalla/PostGIS routes and active OpenStreetMap-derived enrichment for surface, surface quality, sidewalk presence, lighting tags, sparse numeric slope data, and OSM crossing way counts. Advanced safety layers for curb risk, measured traffic, pedestrian density, micromobility zones, production weather risk, and telemetry confidence are not active by default and do not affect scoring unless a real validated source/provider is enabled.

## Public Beta Data Status

SafeRoute is ready for public beta / self-hosted MVP use. It is not a full public safety launch for every desired safety layer.

Active real enrichment datasets:

- Dataset: `osm-moscow-oblast-tags-20260419`
- Source: OpenStreetMap way tags via the Geofabrik Central Federal District extract
- License: ODbL 1.0; attribution required
- Imported rows: `1,126,588`
- Average confidence: `0.89`
- Dataset: `osm-moscow-oblast-crossings-20260419`
- Source: OpenStreetMap crossing way tags via the Geofabrik Central Federal District extract
- License: ODbL 1.0; attribution required
- Imported rows: `62,328`
- Average confidence: `0.909`

Active real factors:

| Factor | Rows | Source |
|---|---:|---|
| `surface_type` | `1,047,856` | OSM `surface` |
| `surface_quality` | `101,604` | OSM `smoothness` |
| `sidewalk_presence` | `12,424` | OSM `sidewalk`, `sidewalk:left`, `sidewalk:right` |
| `lighting_quality` | `492,436` | OSM `lit` tags, not measured illumination |
| `slope_percent` | `452` | Numeric OSM `incline` percent values only |
| `crossing_count` | `62,328` | Direct OSM crossing ways mapped through `public.moscow_network.osmid` |
| `controlled_crossing_count` | `62,328` | OSM `crossing=*` / signal tags where present |
| `uncontrolled_crossing_count` | `62,328` | OSM crossing ways where tags indicate or imply uncontrolled/unknown |
| `crossing_risk` | `62,328` | Conservative tag-derived crossing risk; node-only crossings are not guessed |

Advanced layers not yet active:

- curb risk / curb density
- measured traffic intensity
- pedestrian density
- micromobility forbidden/slow zones
- weather-sensitive risk by default; optional Open-Meteo integration is available behind `SAFEROUTE_WEATHER_ENABLED=true`
- telemetry confidence

Missing layers stay `null` or absent from route score reasons. They do not create penalties, bonuses, UI claims, or green checks.

## Local Run

```bash
./venv/bin/python -m pip install -r requirements-dev.txt
npm run dev:full
```

Open [http://localhost:5173](http://localhost:5173). The Vite dev server proxies `/api/*` and `/route` to `localhost:8000`.

`npm run dev:full` starts Postgres.app on port `5433` when the local Postgres data directory exists, then starts FastAPI and Vite together. It enables public Photon/Valhalla fallback for local development only. Production-like work should use Docker/self-hosted services.

For API-only development:

```bash
npm run dev:api
```

This starts FastAPI on port `8000` using the current environment. It does not start Postgres, Photon, or Valhalla. Use `docker compose up` or `npm run bootstrap:self-hosted` when those real dependencies are required.

## Docker Stack

For the full production-like local checklist, including prerequisites, ports, env, data requirements, and troubleshooting, see [Self-Hosted Backend Stack](docs/SELF_HOSTED.md).

```bash
docker compose up
```

The base compose stack is the production-like local runtime:

- `frontend` serves the built app through `vite preview`
- `api` runs without `--reload`
- public fallback is disabled by default
- source code is baked into images instead of bind-mounted

Postgres starts with PostGIS and pgRouting enabled. The full self-hosted bootstrap copies the existing Moscow safety graph from the local host DB into the compose DB, prepares the production routing columns/indexes, waits for Photon and Valhalla, and then runs the bundled smoke.

`/api/health` reports `fallback` when a dev process is using public Photon/Valhalla after a local dependency failed. Treat that as `degraded`: good enough for local UI work, not production readiness.

For development overrides with bind mounts, API reload, Vite dev server, and optional public fallback:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

## Self-Hosted Moscow+Oblast Data

Production-like local work must run without public Photon/Valhalla fallback:

```bash
npm run self-hosted:preflight
npm run bootstrap:self-hosted
```

Or step-by-step:

```bash
npm run self-hosted:up
npm run self-hosted:ps
npm run self-hosted:logs
```

For data bootstrap internals:

```bash
scripts/data/download-osm.sh
scripts/data/extract-moscow-oblast.sh
scripts/data/import-safety-graph.sh
scripts/data/build-routing-stack.sh
npm run db:graph-export
npm run db:graph-restore
npm run bootstrap:check
npm run bootstrap:fresh
```

The bootstrap pipeline:

- downloads the official Geofabrik Central Federal District PBF,
- extracts Moscow+Oblast with `osmium`,
- imports `public.moscow_network` from `postgresql://artem@localhost:5433/artem` into the compose DB on `5434`,
- applies `scripts/prepare-production-db.sql`,
- starts the Docker stack with `ALLOW_PUBLIC_SERVICE_FALLBACK=false`,
- waits for `GET /api/health?deep=true`,
- runs `scripts/smoke-self-hosted.sh`.

Photon remains self-hosted in Docker, but its local index is bootstrapped inside the container volume on first start. Valhalla uses the repo-local `data/osm/moscow-oblast.osm.pbf` extract directly.

Fresh bootstrap from empty Docker volumes requires a real `public.moscow_network` source. Supported sources are `SOURCE_DATABASE_URL` pointing at a real PostGIS database, or `GRAPH_DUMP_FILE=data/graph/moscow_network.dump` produced by `npm run db:graph-export`. If neither exists, `npm run bootstrap:check` and `npm run bootstrap:fresh` fail with `GRAPH_BOOTSTRAP_REQUIRED` instead of creating fake graph rows.

For route query profiling:

```bash
DATABASE_URL=postgresql://artem@localhost:5433/artem ./venv/bin/python scripts/profile-safe-route.py
```

## Backend Shape

The live API package is under `app/`; root `main.py` is only a compatibility entrypoint for `uvicorn main:app`.

```text
app/api        HTTP routers
app/core       settings, database, observability
app/schemas    Pydantic API contracts
app/services   routing, search, health, telemetry
```

Legacy folders `backend/` and `saferoute-core/` are not live runtime paths.

## Test

Backend verification status and exact pass/fail criteria are tracked in [Backend Verification](docs/BACKEND_VERIFICATION.md).

```bash
npm run lint
npm run check:trust-copy
npm run check:release-readiness
npm run typecheck:backend
npm run test:backend
npm run db:telemetry-check
npm run db:migrate
npm run db:migration-check
npm run db:graph-check
npm run db:graph-source-check
npm run db:enrichment-check
npm run build
npm run smoke:api
npm run smoke:self-hosted
npm run route:corpus-check
npm run perf:route-smoke
npm run perf:telemetry-smoke
npm run bootstrap:self-hosted
npm run self-hosted:preflight
npm run self-hosted:check
```

`npm run smoke:api` checks a real running API process and does not fake dependencies; it fails with startup instructions if `127.0.0.1:8000` is not reachable. `npm run smoke:self-hosted` runs the full dependency and routing smoke and requires PostGIS with `moscow_network`, Photon, and Valhalla to be healthy.

Backend-only passing state is `npm run check:backend` plus `npm run smoke:api` against a real `npm run dev:api` process. In that mode `/api/health` may be `degraded` when PostGIS, Photon, and Valhalla are not running. Full self-hosted passing state requires `npm run self-hosted:preflight` and `npm run smoke:self-hosted` to pass with real Docker/PostGIS/Photon/Valhalla services.

`npm run test:e2e` runs the Playwright browser smoke against `APP_URL` or `http://127.0.0.1:5173/`.
`npm run check:full` chains the static checks plus API and browser smoke against a running local stack.

## Docs

- [Architecture](docs/architecture.md)
- [Auth And Rate-Limit Rollout](docs/AUTH_RATE_LIMIT_PLAN.md)
- [Backend Production Readiness](docs/BACKEND_PRODUCTION_READINESS.md)
- [Backend Verification](docs/BACKEND_VERIFICATION.md)
- [Graph Data Quality](docs/GRAPH_DATA_QUALITY.md)
- [Graph Bootstrap Requirement](docs/GRAPH_BOOTSTRAP_REQUIRED.md)
- [Enrichment Data Model](docs/ENRICHMENT_DATA.md)
- [Enrichment Sources](docs/ENRICHMENT_SOURCES.md)
- [Scoring Factors](docs/SCORING_FACTORS.md)
- [Trust Architecture](docs/TRUST_ARCHITECTURE.md)
- [Explainability Model](docs/EXPLAINABILITY_MODEL.md)
- [Beta Safety Limits](docs/BETA_SAFETY_LIMITS.md)
- [Privacy And Telemetry](docs/PRIVACY_AND_TELEMETRY.md)
- [Public Beta Readiness](docs/PUBLIC_BETA_READINESS.md)
- [Release Checklist](docs/RELEASE_CHECKLIST.md)
- [Production Readiness Gaps](docs/PRODUCTION_READINESS_GAPS.md)
- [Observability](docs/OBSERVABILITY.md)
- [Scoring Governance](docs/SCORING_GOVERNANCE.md)
- [Data Freshness Policy](docs/DATA_FRESHNESS_POLICY.md)
- [Incident Response](docs/INCIDENT_RESPONSE.md)
- [Security Review](docs/SECURITY_REVIEW.md)
- [Weather Risk](docs/WEATHER_RISK.md)
- [Telemetry Confidence](docs/TELEMETRY_CONFIDENCE.md)
- [Public Beta Release Notes](docs/PUBLIC_BETA_RELEASE_NOTES.md)
- [Data Attribution](docs/DATA_ATTRIBUTION.md)
- [Full Safety Launch Roadmap](docs/FULL_SAFETY_LAUNCH_ROADMAP.md)
- [Migration Plan](docs/MIGRATION_PLAN.md)
- [Public Launch Security](docs/SECURITY_PUBLIC_LAUNCH.md)
- [Production Security Env](docs/SECURITY_PRODUCTION_ENV.md)
- [Public Launch Operations](docs/OPERATIONS_PUBLIC_LAUNCH.md)
- [Route Quality Corpus](docs/ROUTE_QUALITY_CORPUS.md)
- [Backup And Restore](docs/BACKUP_RESTORE.md)
- [Incident Runbook](docs/RUNBOOK.md)
- [Routing and Safety](docs/routing-safety.md)
- [Scoring Roadmap](docs/scoring-roadmap.md)
- [Self-Hosted Backend Stack](docs/SELF_HOSTED.md)
- [Frontend Motion System](docs/frontend-motion.md)
- [Figma Handoff](docs/figma-handoff.md)
- [Operations Runbook](docs/operations.md)
- [Telemetry And Edge Roadmap](docs/telemetry-edge.md)
- [Transit Roadmap](docs/transit-roadmap.md)
- [Official References](docs/references.md)
