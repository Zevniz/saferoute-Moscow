# SafeRoute

SafeRoute is a Moscow-first routing and sidewalk-telemetry platform with a real browser-facing FastAPI gateway, Valhalla maneuvers, Photon search, PostGIS/pgRouting safety enrichment, and H3 sidewalk-quality aggregation.

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
npm run typecheck:backend
npm run test:backend
npm run build
npm run smoke:api
npm run smoke:self-hosted
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
- [Backend Production Readiness](docs/BACKEND_PRODUCTION_READINESS.md)
- [Backend Verification](docs/BACKEND_VERIFICATION.md)
- [Routing and Safety](docs/routing-safety.md)
- [Scoring Roadmap](docs/scoring-roadmap.md)
- [Self-Hosted Backend Stack](docs/SELF_HOSTED.md)
- [Frontend Motion System](docs/frontend-motion.md)
- [Figma Handoff](docs/figma-handoff.md)
- [Operations Runbook](docs/operations.md)
- [Telemetry And Edge Roadmap](docs/telemetry-edge.md)
- [Transit Roadmap](docs/transit-roadmap.md)
- [Official References](docs/references.md)
