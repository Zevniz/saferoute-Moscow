# Backend Verification

This document records the current backend/self-hosted verification state and the command order for future local checks.

It is intentionally strict: commands must exercise real code and real services. Do not treat a missing Docker daemon, missing PostGIS graph, unreachable API, or unavailable Photon/Valhalla as success.

## Current Verified State

Last local verification snapshot: 2026-04-25.

- Shell syntax checks passed for backend/self-hosted scripts.
- `package.json` parsed as valid JSON.
- `docker compose config` passed.
- Docker Desktop daemon was started and responded to `docker info`.
- `docker compose build api` passed.
- `npm run check:backend` passed:
  - `npm run lint`: ok.
  - `npm run typecheck:backend`: pyright reported `0 errors, 0 warnings, 0 informations`.
- `npm run test:backend`: `91 passed`.
- `npm run self-hosted:preflight` passed against the running compose stack with 0 failures. It warned that the host source DB was unavailable and that compose ports were already in use by the running stack, but the compose DB already contained the real prepared graph.
- Compose PostGIS was verified with PostGIS and pgRouting extensions.
- Compose PostGIS contained `public.moscow_network` with `1,579,570` rows.
- Compose PostGIS contained prepared routing columns and materialized view `public.moscow_network_nodes`.
- Telemetry schema was applied idempotently against compose Postgres with `npm run db:telemetry-schema`; the script selected the reachable compose DB on `127.0.0.1:5434`.
- Telemetry schema can be verified read-only with `npm run db:telemetry-check`.
- Graph assets can be verified read-only with `npm run db:graph-check`.
- Fresh-bootstrap graph source databases can be verified read-only with `npm run db:graph-source-check`.
- A real local graph dump exists at `data/graph/moscow_network.dump` with manifest metadata:
  - rows: `1,579,570`
  - SRID: `4326`
  - sha256: `fc28847e08f78f94ce54908324ff3f1905a56ba48c385e30224d2b6f1a4c3a2e`
- `npm run bootstrap:fresh` passed with an isolated compose project and empty fresh volumes:
  - restored the real dump into a fresh PostGIS volume;
  - prepared routing metadata and `public.moscow_network_nodes`;
  - applied Alembic app-owned baseline;
  - verified telemetry, enrichment, and graph schema;
  - started isolated API, DB, frontend, Photon, and Valhalla on non-conflicting ports;
  - passed `smoke:api` and `smoke:self-hosted` against `http://127.0.0.1:18000`.
- Photon downloaded and served the real Russia Photon index.
- Valhalla built and served real tiles from `data/osm/moscow-oblast.osm.pbf`.
- API `/api/health?deep=true` returned `status: ok` with Postgres, Photon, Valhalla, and `walk`/`bike`/`car` profile readiness all `ok`.
- `npm run smoke:api` passed against the running compose API with `health: ok`.
- `npm run smoke:self-hosted` passed against the full compose stack.
- Browser smoke against `http://127.0.0.1:5173` passed: search, route cards, navigation start/end, console/page-error checks, and score rendering were verified.
- Browser mode switching passed for `safest`, `fastest`, `balanced`, and `accessible`; each mode triggered a real `/api/route` request and rendered `Score N/100` on route cards.

Current expected caveat:

- The default host source DB at `postgresql://artem@localhost:5433/artem` did not pass `npm run db:graph-source-check` during this snapshot. This does not block the current compose stack or fresh bootstrap from the real local dump, but a public deployment still needs either a reachable official `SOURCE_DATABASE_URL` or a published/versioned real graph dump artifact.

## Public-Launch Hardening Verification Snapshot

Last full hardening verification: 2026-04-25.

Commands run and observed results:

```text
bash -n scripts/*.sh                         ok
node package.json parse                       ok
docker version                                ok, Docker 29.2.1 / Docker Desktop 4.65.0
docker info                                   ok
docker compose config                         ok
docker compose build api                      ok
docker compose build frontend                 ok
npm run build                                 ok, Vite built with existing large-chunk warning
npm run check:backend                         ok, lint ok, pyright 0 errors, 91 passed
npm run self-hosted:down && self-hosted:up    ok
docker compose ps                             api/db/frontend/photon/valhalla healthy
npm run self-hosted:preflight                 ok, 0 failures, 6 warnings for already-used ports/source DB
npm run db:migrate                            ok
npm run db:migration-check                    ok, Alembic head 0001_app_schema_baseline
npm run db:telemetry-schema                   ok
npm run db:telemetry-schema                   ok, idempotent repeat
npm run db:telemetry-check                    ok
npm run db:enrichment-check                   ok, schema present, 0 active enrichment rows
npm run db:graph-check                        ok, 1,579,570 edges, 547,793 nodes
npm run bootstrap:check                       ok, real graph dump available
npm run db:graph-source-check                 expected fail for default localhost:5433 source DB
npm run smoke:api                             ok, health ok
npm run smoke:self-hosted                     ok, walk/bike/car full mode
npm run route:corpus-check                    ok, 16 real route/mode cases
npm run perf:route-smoke                      ok, p95 11ms on warmed local route cache
npm run perf:telemetry-smoke                  ok, p95 20ms read-path smoke
APP_URL=http://127.0.0.1:5173 npm run test:e2e ok, routeCards=2, consoleIssues=[]
npm run bootstrap:fresh                       ok, isolated empty-volume bootstrap from real dump
```

Fresh-bootstrap facts observed from the isolated project:

- `public.moscow_network`: `1,579,570` rows.
- `public.moscow_network_nodes`: `547,793` rows.
- PostGIS and pgRouting extensions were present.
- Geometry SRID was `4326`.
- Required graph indexes and prepared A* columns were present.
- The isolated full smoke used `http://127.0.0.1:18000` and returned walk `2`, bike `1`, and car `3` real routes.

## Backend-Only Passing Definition

Backend-only mode verifies the FastAPI code, API process surface, type baseline, lint guardrails, and unit/contract tests. It does not prove production-like routing readiness.

Backend-only is passing when all of these are true:

1. `npm run check:backend` exits successfully.
2. A real API process is running from `npm run dev:api`.
3. `npm run smoke:api` exits successfully against that process.

`/api/health` may return `status: degraded` in backend-only mode when Postgres, Photon, or Valhalla are not running. That degraded state is acceptable for API-process verification, but it is not self-hosted readiness.

Recommended command order:

```bash
npm run check:backend
```

In a second terminal:

```bash
npm run dev:api
```

Then:

```bash
npm run smoke:api
```

Stop the API process after the smoke check.

## Full Self-Hosted Passing Definition

Full self-hosted mode verifies the production-like local stack without public Photon/Valhalla fallback.

Full self-hosted is passing only when all of these are true:

1. Docker daemon is running.
2. `npm run self-hosted:preflight` exits successfully.
3. PostGIS contains real `public.moscow_network` data.
4. Photon is healthy.
5. Valhalla is healthy and can route `walk`, `bike`, and `car`.
6. API `/api/health?deep=true` returns `status: ok`.
7. `npm run smoke:self-hosted` exits successfully.

Recommended command order after Docker daemon is running:

```bash
npm run self-hosted:preflight
npm run bootstrap:self-hosted
```

If the compose DB is already prepared and the OSM/graph data is already present:

```bash
npm run self-hosted:up
npm run self-hosted:ps
npm run smoke:self-hosted
```

For an existing database that did not run Docker init scripts, apply telemetry schema explicitly:

```bash
DATABASE_URL=postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db npm run db:telemetry-schema
DATABASE_URL=postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db npm run db:telemetry-check
DATABASE_URL=postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db npm run db:migrate
DATABASE_URL=postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db npm run db:migration-check
DATABASE_URL=postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db npm run db:enrichment-check
```

If `DATABASE_URL` is omitted, the script uses the running compose DB when it is reachable and otherwise falls back to the host local default.

Verify the real routing graph:

```bash
DATABASE_URL=postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db npm run db:graph-check
```

`npm run db:graph-check` is read-only. It fails if PostGIS/pgRouting, `public.moscow_network`, required columns, geometry/SRID, prepared routing columns, `public.moscow_network_nodes`, or required graph indexes are missing.

Verify a fresh-bootstrap source graph before import:

```bash
SOURCE_DATABASE_URL=postgresql://user:pass@host:5432/db npm run db:graph-source-check
```

`npm run db:graph-source-check` is read-only. It fails if the source DB is unreachable or lacks real `public.moscow_network` rows, required base columns, geometry/SRID, populated `safety_weight`, or routing-prep eligible geometry/length values.

Verify whether fresh bootstrap can run from an empty compose project:

```bash
npm run bootstrap:check
npm run bootstrap:fresh
```

These commands require either a valid `SOURCE_DATABASE_URL` or a real `GRAPH_DUMP_FILE`. Without one they fail with `GRAPH_BOOTSTRAP_REQUIRED`; that failure is expected and honest, not a passing public-launch state.

## Why Health Can Be Degraded

`/api/health` checks real dependencies:

- PostGIS and `public.moscow_network`.
- Photon.
- Valhalla.
- Optional per-profile Valhalla route readiness for deep checks.

When the API process is running but one of those dependencies is unavailable, health returns `degraded`. This is useful for local backend work because `npm run smoke:api` can still confirm that the API process, metrics endpoint, and validation behavior are real.

For production-like self-hosted verification, degraded health is a failure. Compose API healthcheck also requires JSON `status: "ok"`.

## Script Truthfulness Checks

The verification scripts are expected to fail loudly rather than hide missing infrastructure:

- `npm run check:backend` runs real lint, pyright, and pytest. It is not a no-op.
- `npm run smoke:api` makes real HTTP requests to `/api/health`, `/api/metrics`, and `/api/search`; it fails if the API is unreachable.
- `npm run self-hosted:preflight` checks Docker CLI, Docker daemon, compose config, required init/schema files, OSM extract, PostgreSQL client tools, PostGIS/pgRouting extensions, `public.moscow_network`, prepared routing metadata, ports, and optional API health. It fails on critical missing requirements.
- `npm run db:telemetry-check` queries the real database and fails if expected telemetry tables, columns, primary keys, or indexes are missing.
- `npm run db:graph-check` queries the real database and fails if required routing graph assets are missing. It also prints current graph coverage and enrichment gaps.
- `npm run db:graph-source-check` queries only the configured source database and fails before graph import can drop/reload target data.
- `npm run db:migrate` applies the non-destructive Alembic app-owned baseline for telemetry and enrichment schema.
- `npm run db:migration-check` fails if the database is not at Alembic head.
- `npm run db:enrichment-check` queries real enrichment tables and prints active dataset/row coverage. Empty coverage is allowed but means enrichment factors remain inactive.
- `npm run smoke:self-hosted` runs full smoke mode and requires API health `ok`, service statuses `ok`, route profile readiness, real search, sidewalk cells, walk/bike/car routes, real maneuver instructions, duplicate-geometry checks, fast-route correctness, and cache metrics.
- `npm run route:corpus-check` calls real `/api/route` across multiple profiles and all routing modes, but checks stable properties rather than brittle geometry snapshots.
- `npm run perf:route-smoke` and `npm run perf:telemetry-smoke` perform local latency sanity checks without claiming production SLA.

## Next Steps For A Fresh Machine

1. Start Docker Desktop or the local Docker service.
2. Run `npm run self-hosted:preflight`.
3. Run `npm run bootstrap:check`.
4. If bootstrap reports missing `public.moscow_network`, provide `SOURCE_DATABASE_URL` or restore a real `GRAPH_DUMP_FILE`.
5. Run `npm run bootstrap:fresh` to verify isolated empty-volume bootstrap, or `npm run self-hosted:up` if the compose DB and OSM/Photon/Valhalla volumes are already prepared.
6. Run `npm run db:migrate`, `npm run db:migration-check`, `npm run db:telemetry-check`, `npm run db:enrichment-check`, and `npm run db:graph-check`.
7. Run `npm run smoke:self-hosted`, `npm run route:corpus-check`, and the browser smoke as final confirmation.

Separate future work:

- Provide and version the official graph dump/source for public deployments.
- Enable the documented auth/rate-limit policy in production deployment config.
- Import a real edge-mapped enrichment dataset; until then advanced factors remain inactive.
- Expand the real route corpus and add production monitoring once public traffic exists.

See [Backend Production Readiness](BACKEND_PRODUCTION_READINESS.md) for the current migration and auth/rate-limit plan.
