# Self-Hosted Backend Stack

This guide is the reproducible local path for running SafeRoute without public Photon or Valhalla fallback. It is intended for backend verification, route smoke tests, and production-like local debugging.

The stack uses real services and real data only. It does not create fake route data, fake endpoints, or mock production services.

## Prerequisites

- Docker CLI and Docker daemon. Docker Desktop must be running on macOS/Windows before compose commands can work.
- Docker Compose through `docker compose`.
- Node/npm. The compose frontend image uses Node 20; local development has been exercised with modern Node.
- Python. The API container uses Python 3.11; local `npm run dev:api` uses `./venv/bin/python`.
- PostgreSQL client tools: `psql` and `pg_dump`. They are required to import `public.moscow_network` into the compose PostGIS database and to apply telemetry schema manually.
- `curl` for smoke checks and service readiness checks.
- `osmium` if the Moscow+Oblast OSM extract must be rebuilt. On macOS: `brew install osmium-tool`.
- Disk and network budget for OSM/Photon/Valhalla. The current local Central Federal District PBF is hundreds of MB, the Moscow+Oblast extract is hundreds of MB, and service indexes/tiles can require additional GBs in Docker volumes.

Run the preflight first:

```bash
npm run self-hosted:preflight
```

Preflight fails on critical missing requirements. It may warn about ports that are already listening because that can also mean the stack is already running.

For the current backend-only and self-hosted pass/fail criteria, see [Backend Verification](BACKEND_VERIFICATION.md).

## Services

| Service | Compose name | Purpose |
| --- | --- | --- |
| FastAPI | `api` | Public API gateway under `/api/*`, `/route`, metrics, health, telemetry, and tiles. |
| PostGIS/pgRouting | `db` | Safety graph database and telemetry tables. |
| Photon | `photon` | Self-hosted search and reverse geocoding. |
| Valhalla | `valhalla` | Self-hosted routing and maneuver source. |
| Frontend | `frontend` | Built Vite app served by `vite preview`. |

## Ports

| Port | Service | Notes |
| --- | --- | --- |
| `8000` | API | `http://127.0.0.1:8000/api/health` |
| `5173` | Frontend | `http://127.0.0.1:5173` |
| `5434` | Compose Postgres | Container port `5432`, host port `5434`. |
| `2322` | Photon | `http://127.0.0.1:2322/api?q=Москва&limit=1` |
| `8002` | Valhalla | `http://127.0.0.1:8002/status` |

Local API-only defaults outside Docker use Postgres on `localhost:5433`. The compose database is intentionally exposed on `localhost:5434` to avoid colliding with that host database.

## Environment

Copy `.env.example` for local API work when needed:

```bash
cp .env.example .env
```

Important variables:

| Variable | Default | Required for |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql://artem@localhost:5433/artem` locally, compose uses `postgresql://saferoute:saferoute_pass@db:5432/saferoute_db` | API database access. |
| `SOURCE_DATABASE_URL` | `postgresql://artem@localhost:5433/artem` | Importing real `public.moscow_network` into compose PostGIS. |
| `TARGET_DATABASE_URL` | `postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db` | Import target for compose PostGIS. |
| `PHOTON_URL` | `http://localhost:2322` locally, compose uses `http://photon:2322` | Search and reverse geocoding. |
| `VALHALLA_URL` | `http://localhost:8002` locally, compose uses `http://valhalla:8002` | Route candidates and maneuvers. |
| `ALLOW_PUBLIC_SERVICE_FALLBACK` | `false` for self-hosted | Must stay `false` for production-like verification. |
| `VALHALLA_TILE_URLS` | `file:///custom_files/osm/moscow-oblast.osm.pbf` | Valhalla tile build input in compose. |
| `ROUTE_DATA_VERSION` | `moscow-oblast-v1` or generated from the OSM extract mtime in bootstrap | Route cache invalidation across graph/tile changes. |

Do not put real secrets in committed env files. The compose password is a local development credential only.

## Routing Data

Full route verification requires two independent real data inputs:

1. `data/osm/moscow-oblast.osm.pbf` for Valhalla.
2. `public.moscow_network` in PostGIS for SafeRoute safety scoring and pgRouting.

The OSM extract is repo-local data. If it is missing, `npm run bootstrap:self-hosted` runs:

```bash
scripts/data/download-osm.sh
scripts/data/extract-moscow-oblast.sh
```

The safety graph is not generated from fake data. It must either exist in `SOURCE_DATABASE_URL` as `public.moscow_network`, or be provided as a real `GRAPH_DUMP_FILE` created from a known-good database. The import/restore scripts copy it into the compose DB and then apply production graph preparation:

```bash
scripts/data/import-safety-graph.sh
scripts/data/restore-safety-graph.sh
scripts/prepare-production-db.sql
```

The required base columns are documented in [Routing And Safety](routing-safety.md). Prepared compose databases should also have:

- `cost_walk_safe`
- `cost_bike_safe`
- `cost_car_safe`
- `source_x`
- `source_y`
- `target_x`
- `target_y`
- materialized view `public.moscow_network_nodes`

Check source graph availability:

```bash
SOURCE_DATABASE_URL=postgresql://user:pass@host:5432/db npm run db:graph-source-check
```

Check compose graph availability after import:

```bash
DATABASE_URL=postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db npm run db:graph-check
```

Recommended real dump format for disaster recovery:

```bash
DATABASE_URL=postgresql://user:pass@host:5432/db npm run db:graph-export
```

Restore only into an empty or intentionally rebuilt target database, then prepare and verify:

```bash
GRAPH_DUMP_FILE=data/graph/moscow_network.dump npm run db:graph-restore
```

Check whether a fresh server has a valid source before attempting bootstrap:

```bash
npm run bootstrap:check
```

Run isolated empty-volume bootstrap verification without deleting the working compose volumes:

```bash
npm run bootstrap:fresh
```

## Startup

Recommended full bootstrap:

```bash
npm run self-hosted:preflight
npm run bootstrap:self-hosted
```

`npm run bootstrap:self-hosted` performs the full production-like sequence:

1. Ensures `data/osm/moscow-oblast.osm.pbf` exists, downloading/extracting if needed.
2. Imports real `public.moscow_network` from `SOURCE_DATABASE_URL` into compose PostGIS.
3. Applies `scripts/prepare-production-db.sql`.
4. Starts Photon, Valhalla, API, and frontend with public fallback disabled.
5. Waits for API health.
6. Runs `npm run smoke:self-hosted`.

If data is already prepared and you only need to start containers:

```bash
npm run self-hosted:up
npm run self-hosted:ps
npm run self-hosted:logs
```

Stop the stack:

```bash
npm run self-hosted:down
```

## Telemetry Schema

Fresh compose databases apply:

```text
docker/postgres/init/02_telemetry.sql
```

For an existing database, apply the same idempotent schema explicitly:

```bash
DATABASE_URL=postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db npm run db:telemetry-schema
```

Verify that the real database has the expected telemetry tables, primary keys, and indexes:

```bash
DATABASE_URL=postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db npm run db:telemetry-check
```

Apply and verify app-owned migrations for telemetry/enrichment metadata:

```bash
DATABASE_URL=postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db npm run db:migrate
DATABASE_URL=postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db npm run db:migration-check
DATABASE_URL=postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db npm run db:enrichment-check
```

Verify that the real routing graph has the required PostGIS/pgRouting assets, prepared columns, nodes, indexes, and current scoring-column coverage:

```bash
DATABASE_URL=postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db npm run db:graph-check
```

Verify that a fresh-bootstrap source database is valid before import:

```bash
SOURCE_DATABASE_URL=postgresql://user:pass@host:5432/db npm run db:graph-source-check
```

If `DATABASE_URL` is not set, the script uses the running compose DB on `127.0.0.1:5434` when it is reachable; otherwise it falls back to the host local default on `localhost:5433`.

This is non-destructive DDL using `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`.

## Smoke Checks

API-only smoke:

```bash
npm run smoke:api
```

This checks a real running API process and real public API surfaces. It does not require all dependencies to be healthy, but it does require the API process to be reachable.

In API-only mode, `/api/health` can return `degraded` when PostGIS, Photon, or Valhalla are not running. That is acceptable for `npm run smoke:api`, but it is not full self-hosted readiness.

Full self-hosted smoke:

```bash
npm run smoke:self-hosted
```

This requires:

- API reachable on `API_URL` or `http://127.0.0.1:8000`.
- `/api/health?deep=true` status `ok`.
- PostGIS reachable with `public.moscow_network`.
- Photon reachable and returning real Moscow search results.
- Valhalla reachable and able to route `walk`, `bike`, and `car`.
- Route responses with real maneuver instructions, no duplicate geometry, and route cache metrics.

Combined preflight plus full smoke:

```bash
npm run self-hosted:check
```

`npm run self-hosted:check` is expected to fail until Docker is running and the real PostGIS `public.moscow_network`, Photon, and Valhalla dependencies are available.

## Healthchecks

Compose healthchecks verify real service behavior:

- `db`: `pg_isready` against `saferoute_db`.
- `photon`: HTTP query to `/api?q=Москва&limit=1`.
- `valhalla`: HTTP `/status`.
- `api`: `GET /api/health?deep=false` must return JSON with `status: "ok"`. A reachable but degraded API is intentionally unhealthy for the production-like compose stack.
- `frontend`: HTTP response from Vite preview.

The API healthcheck depends on `public.moscow_network`, Photon, and Valhalla. If the safety graph has not been imported, the API container can remain unhealthy even though the process is running.

## Troubleshooting

Docker daemon not running:

```text
Docker CLI is installed, but the Docker daemon is not responding.
```

Start Docker Desktop or the Docker service for your OS, then rerun:

```bash
npm run self-hosted:preflight
```

Port already in use:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

Stop the conflicting local process, or confirm it is the intended compose service.

Postgres is not ready:

```bash
npm run self-hosted:ps
docker compose logs db
```

If `psql` cannot connect to `localhost:5433`, that is the host source DB, not the compose DB. Start the host DB or set `SOURCE_DATABASE_URL` to the database that contains real `public.moscow_network`.

Compose Postgres cannot be reached on `localhost:5434`:

```bash
docker compose up -d db
docker compose logs db
```

Photon is not ready:

```bash
curl "http://127.0.0.1:2322/api?q=Москва&limit=1"
docker compose logs photon
```

Photon first start can take time while indexes are prepared in the Docker volume.

Valhalla is not ready:

```bash
curl "http://127.0.0.1:8002/status"
docker compose logs valhalla
```

Confirm the OSM extract exists:

```bash
ls -lh data/osm/moscow-oblast.osm.pbf
```

Missing `moscow_network`:

```bash
psql "$SOURCE_DATABASE_URL" -Atqc "SELECT count(*) FROM public.moscow_network;"
```

If the table is missing, restore or build the real safety graph first. Do not create fake graph data to satisfy smoke checks.

API returns connection refused:

```bash
npm run self-hosted:ps
docker compose logs api
```

For API-only work, run:

```bash
npm run dev:api
```

For full self-hosted work, run:

```bash
npm run bootstrap:self-hosted
```

`npm run db:telemetry-schema` cannot connect:

The default `DATABASE_URL` points at host Postgres on `localhost:5433`. For compose Postgres, use:

```bash
DATABASE_URL=postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db npm run db:telemetry-schema
```

`npm run db:graph-check` fails:

- If `public.moscow_network` is missing, restore/import the real graph with `npm run bootstrap:self-hosted` and a valid `SOURCE_DATABASE_URL`.
- If prepared routing columns or `public.moscow_network_nodes` are missing, run `scripts/prepare-production-db.sql` against the real target DB.
- If optional scoring enrichment columns are missing, this is not a graph-check failure. Those product factors remain inactive until real data is loaded.

`npm run db:graph-source-check` fails:

- Set `SOURCE_DATABASE_URL` to a real source DB with `public.moscow_network`.
- If using a dump instead of a source DB, restore that real dump into a database first; the check intentionally does not invent placeholder graph rows.
- Required source columns are `id`, `u`, `v`, `highway`, `length`, `safety_weight`, and `geometry` with SRID `4326`.

Full self-hosted smoke still fails after containers are up:

Check health first:

```bash
curl http://127.0.0.1:8000/api/health?deep=true
```

Any `degraded`, `error`, or `fallback` status means the full self-hosted stack is not production-ready yet.
