# Backend Verification

This document records the current backend/self-hosted verification state and the command order for future local checks.

It is intentionally strict: commands must exercise real code and real services. Do not treat a missing Docker daemon, missing PostGIS graph, unreachable API, or unavailable Photon/Valhalla as success.

## Current Verified State

Last local verification snapshot: 2026-04-24.

- Shell syntax checks passed for backend/self-hosted scripts.
- `package.json` parsed as valid JSON.
- `docker compose config` passed.
- Docker Desktop daemon was started and responded to `docker info`.
- `docker compose build api` passed.
- `npm run check:backend` passed:
  - `npm run lint`: ok.
  - `npm run typecheck:backend`: pyright reported `0 errors, 0 warnings, 0 informations`.
  - `npm run test:backend`: `36 passed`.
- `npm run self-hosted:preflight` passed against the running compose stack. It warned that the host source DB was unavailable, but the compose DB already contained the real prepared graph.
- Compose PostGIS was verified with PostGIS and pgRouting extensions.
- Compose PostGIS contained `public.moscow_network` with `1,579,570` rows.
- Compose PostGIS contained prepared routing columns and materialized view `public.moscow_network_nodes`.
- Telemetry schema was applied idempotently against compose Postgres with `npm run db:telemetry-schema`; the script selected the reachable compose DB on `127.0.0.1:5434`.
- Telemetry schema can be verified read-only with `npm run db:telemetry-check`.
- Photon downloaded and served the real Russia Photon index.
- Valhalla built and served real tiles from `data/osm/moscow-oblast.osm.pbf`.
- API `/api/health?deep=true` returned `status: ok` with Postgres, Photon, Valhalla, and `walk`/`bike`/`car` profile readiness all `ok`.
- `npm run smoke:api` passed against the running compose API with `health: ok`.
- `npm run smoke:self-hosted` passed against the full compose stack.

Current expected caveat:

- The host source DB at `postgresql://artem@localhost:5433/artem` was not reachable during this snapshot. This does not block the current compose stack because its Docker volume already contains real `public.moscow_network`, but rebuilding/importing the graph from scratch still requires a real `SOURCE_DATABASE_URL` or another documented real data source.

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
```

If `DATABASE_URL` is omitted, the script uses the running compose DB when it is reachable and otherwise falls back to the host local default.

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
- `npm run smoke:self-hosted` runs full smoke mode and requires API health `ok`, service statuses `ok`, route profile readiness, real search, sidewalk cells, walk/bike/car routes, real maneuver instructions, duplicate-geometry checks, fast-route correctness, and cache metrics.

## Next Steps For A Fresh Machine

1. Start Docker Desktop or the local Docker service.
2. Run `npm run self-hosted:preflight`.
3. If preflight reports missing `public.moscow_network`, start or restore the source DB and set `SOURCE_DATABASE_URL`, or ensure the compose DB already contains the real graph.
4. Run `npm run bootstrap:self-hosted` for the full data import/start/smoke path, or `npm run self-hosted:up` if the compose DB and OSM/Photon/Valhalla volumes are already prepared.
5. Run `npm run smoke:self-hosted` as the final confirmation.

Separate future work:

- Design a safe Alembic or migration plan for live backend schema management.
- Make a product/security decision for auth and rate limiting on telemetry, metrics, and tiles.
- Perform real route verification with the actual PostGIS/Photon/Valhalla stack and real Moscow data.

See [Backend Production Readiness](BACKEND_PRODUCTION_READINESS.md) for the current migration and auth/rate-limit plan.
