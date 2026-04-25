# Operations Runbook

## Environment

Copy `.env.example` and override as needed:

```bash
DATABASE_URL=postgresql://artem@localhost:5433/artem
PHOTON_URL=http://localhost:2322
VALHALLA_URL=http://localhost:8002
ALLOW_PUBLIC_SERVICE_FALLBACK=false
HTTP_USER_AGENT="SafeRoute/2.0 local"
```

For production-like local work, use self-hosted Photon and Valhalla via Docker Compose. Public endpoints are only a development fallback through `ALLOW_PUBLIC_SERVICE_FALLBACK=true`.

When fallback is enabled, `/api/health` reports `status: fallback` for any dependency or route profile that succeeded through a public endpoint instead of the configured self-hosted URL. Overall health becomes `degraded` so production checks do not mistake fallback traffic for a healthy local stack.

`/api/health` redacts database passwords in its reported Postgres URL. Keep dependency URLs useful for debugging, but never expose credentials in health responses or logs.

## Install Local Tooling

```bash
python3 -m venv venv
./venv/bin/python -m pip install -r requirements-dev.txt
npm ci
```

`requirements.txt` contains runtime API dependencies. `requirements-dev.txt` is the local backend dependency entrypoint; backend typechecking runs through the Node dev dependency `pyright`.

## Start The API Only

```bash
npm run dev:api
```

The API listens on `http://127.0.0.1:8000` by default. This command starts only FastAPI; it does not start Postgres, Photon, or Valhalla. `/api/health` can still return `degraded` while the API process itself is reachable.

Use this API-only smoke to verify the process and public API surface:

```bash
npm run smoke:api
```

If the API is not reachable, the smoke exits non-zero and prints the startup commands.

## Start Full Local UI Development

```bash
npm run dev:full
```

`npm run dev:full` starts the API and Vite. It attempts to start Postgres.app when available and enables public Photon/Valhalla fallback for local UI work.

## Start With Docker

For the complete self-hosted local guide, use [Self-Hosted Backend Stack](SELF_HOSTED.md). It includes prerequisites, ports, environment variables, data requirements, smoke checks, and troubleshooting.

```bash
docker compose up
```

The base compose file is the production-like local profile: built frontend, non-reload API, and fallback disabled. Use `docker-compose.dev.yml` only for live code iteration.

The first Valhalla and Photon starts can take a long time because they download and build OSM-derived data. Keep the terminal open until the services report ready state.

For live development:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

## Build Self-Hosted Moscow+Oblast Runtime

Use the reproducible OSM pipeline for production-like local routing:

```bash
npm run self-hosted:preflight
npm run bootstrap:self-hosted
```

Defaults:

- Upstream PBF: `https://download.geofabrik.de/russia/central-fed-district-latest.osm.pbf`
- Extract bbox: `35.0,54.0,40.5,57.2`
- Extract path: `data/osm/moscow-oblast.osm.pbf`
- Runtime fallback: disabled through `ALLOW_PUBLIC_SERVICE_FALLBACK=false`
- Source safety graph DB: `postgresql://artem@localhost:5433/artem`
- Target compose DB: `postgresql://saferoute:saferoute_pass@localhost:5434/saferoute_db`

If `osmium` is missing:

```bash
brew install osmium-tool
```

When the graph and OSM data are already prepared, the container lifecycle shortcuts are:

```bash
npm run self-hosted:up
npm run self-hosted:ps
npm run self-hosted:logs
npm run self-hosted:down
```

## Load Safety Data Into Docker Postgres

The compose DB starts with PostGIS and pgRouting extensions. The standard bootstrap path copies `public.moscow_network` from the host DB and prepares it automatically:

```bash
scripts/data/import-safety-graph.sh
```

The script:

- starts compose PostGIS if needed,
- drops stale compose copies of `moscow_network`,
- copies the schema and data from `postgresql://artem@localhost:5433/artem`,
- applies `scripts/prepare-production-db.sql`,
- verifies row count, cost columns, and `moscow_network_nodes`.

If you need to force a full re-import:

```bash
FORCE_DB_IMPORT=true scripts/data/import-safety-graph.sh
```

Then verify:

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/metrics
curl "http://localhost:8000/api/search?q=парк&limit=3"
curl "http://localhost:8000/api/route?lat1=55.7558&lon1=37.6173&lat2=55.75&lon2=37.6&profile=walk&mode=safest&alternatives=3"
curl -X POST http://localhost:8000/api/telemetry/sidewalk-samples \
  -H 'content-type: application/json' \
  -d '{"samples":[{"device_id":"robot-1","captured_at":"2026-04-20T12:00:00Z","lat":55.7558,"lon":37.6173,"speed_mps":1.1,"source":"robot","surface_score":92,"gps_accuracy_m":8}]}'
```

Or run the bundled smoke:

```bash
npm run smoke:self-hosted
```

`npm run smoke:self-hosted` requires a real running API plus healthy PostGIS, Photon, Valhalla, and per-profile Valhalla route readiness. It checks real search, sidewalk-cell reads, walk/bike/car routes, maneuver instructions, duplicate route geometry, fast-route truthfulness, and route cache metrics.

## Telemetry Schema

Fresh Docker Postgres databases apply telemetry tables from:

```text
docker/postgres/init/02_telemetry.sql
```

For an existing database, apply the same idempotent schema manually:

```bash
DATABASE_URL=postgresql://artem@localhost:5433/artem npm run db:telemetry-schema
```

Then verify schema presence without applying DDL:

```bash
DATABASE_URL=postgresql://artem@localhost:5433/artem npm run db:telemetry-check
```

When `DATABASE_URL` is not set, the schema script first checks the running compose DB on `127.0.0.1:5434` and uses it if available; otherwise it falls back to the host local default on `localhost:5433`.

The runtime still keeps a backward-compatible idempotent schema fallback before telemetry reads/writes, but production-like environments should apply the schema explicitly during setup.

## Backend Static Checks

For the final backend/self-hosted verification checklist and current expected-fail state, see [Backend Verification](BACKEND_VERIFICATION.md).

```bash
npm run lint
npm run typecheck:backend
npm run test:backend
```

`npm run typecheck:backend` runs pyright with the baseline in `pyrightconfig.json`.

## Failure Modes

- `postgres: error`: DB is down or `moscow_network` is missing.
- `photon: error`: search and reverse geocoding are unavailable.
- `valhalla: error`: route candidates and maneuver narratives are unavailable.
- `photon/valhalla: fallback`: the dev fallback handled the request; disable `ALLOW_PUBLIC_SERVICE_FALLBACK` or repair the self-hosted service before production testing.
- `/api/route` returns fewer than 3 routes: the engines found fewer unique real candidates.
- `/api/route` returns 404: no viable real route exists for the selected pair/profile.
- `/api/telemetry/sidewalk-samples` returns 503: telemetry tables cannot be created or written.

## Cold Restart Checklist

1. Start Postgres and confirm `moscow_network` exists.
2. Start Photon and Valhalla.
3. Start FastAPI.
4. Start Vite.
5. Verify `/api/health`.
6. Build one route per profile: `walk`, `bike`, `car`.

For the production-like local self-hosted cutover, use `npm run bootstrap:self-hosted` instead of doing the steps manually.

## Performance Profiling

After `scripts/prepare-production-db.sql`, safe routing prefers `pgr_aStar` when endpoint coordinate columns exist and falls back to Dijkstra only after a technical failure.

```bash
DATABASE_URL=postgresql://artem@localhost:5433/artem ./venv/bin/python scripts/profile-safe-route.py
```

Targets for the Moscow MVP:

- Warm cached route: `<300ms`
- Warm uncached local Valhalla route: `<1500ms`
- Cold safe-route geometry: `<4000ms`; slower plans should be tracked with the EXPLAIN output.
