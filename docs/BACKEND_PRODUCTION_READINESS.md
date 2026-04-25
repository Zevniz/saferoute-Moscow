# Backend Production Readiness

This document captures the next backend hardening phase after the full self-hosted stack was verified with real PostGIS, Photon, Valhalla, and Moscow routing data.

The rule for this repo stays strict: prefer smaller changes that are real, non-destructive, and verifiable. Do not add fake services, fake graph data, placeholder endpoints, or scripts that report success without exercising the real backend.

## Current Backend Shape

- Live API: FastAPI in `app/`, with root `main.py` kept as the `uvicorn main:app` compatibility entrypoint.
- Routes: `app/api/routes.py`.
- Contracts: Pydantic v2 models in `app/schemas/`.
- Services: `app/services/` for search, routing, health, telemetry, geometry, and dependency HTTP calls.
- Settings, DB, metrics, logging: `app/core/`.
- Runtime data stores: PostgreSQL/PostGIS/pgRouting, Photon, Valhalla, in-process route cache, in-process Prometheus text metrics.
- Self-hosted stack: `docker-compose.yml` with API `8000`, frontend `5173`, compose Postgres `5434`, Photon `2322`, Valhalla `8002`.

## Prioritized Audit

Safe to improve now:

- Keep `CORS_ALLOWED_ORIGINS` compatible with both JSON-array compose values and comma-separated `.env` values.
- Make routing detect `public.moscow_network_nodes` when it is a materialized view, so prepared graph metadata is actually used.
- Add a read-only telemetry schema check that verifies the real database instead of relying on runtime lazy DDL.
- Document the migration, auth/rate-limit, disaster recovery, observability, API robustness, test, and DB safety posture.

Needs product or operational decision:

- Auth and rate limiting for `/api/telemetry/sidewalk-samples`, `/api/metrics`, `/tiles/{z}/{x}/{y}.pbf`, and potentially public read APIs.
- Whether `/api/metrics` remains intentionally unauthenticated in all deployments or becomes protected behind an optional token/proxy.
- Abuse limits for telemetry ingestion and tile reads. These should be configurable and rolled out in observe-only or reverse-proxy mode before hard enforcement.

Needs real external data or environment:

- Fresh rebuild from empty Docker volumes requires a real source containing `public.moscow_network`; current scripts must not create fake graph data.
- Photon first-start readiness depends on its real Docker volume/index bootstrap.
- Valhalla first-start readiness depends on real `data/osm/moscow-oblast.osm.pbf`.

Risky for production and deferred:

- A full Alembic migration system for all schema assets.
- Destructive graph imports or forced reimports of `public.moscow_network`.
- Any API contract change for existing frontend/public clients.
- Enforcing auth/rate limits without a compatibility rollout.

## Migration Plan

Alembic is appropriate long term for ordinary application-owned relational schema, especially telemetry tables and future non-graph tables. It should not be introduced as a rushed replacement for every database asset because this repo also has:

- PostGIS and pgRouting extensions initialized by Docker entrypoint SQL.
- A large externally sourced `public.moscow_network` graph.
- Graph preparation SQL in `scripts/prepare-production-db.sql`.
- Existing idempotent telemetry schema SQL in `docker/postgres/init/02_telemetry.sql`.

Recommended phased plan:

1. Keep the current idempotent telemetry schema as the migration baseline.
2. Use `npm run db:telemetry-schema` to apply that baseline explicitly.
3. Use `npm run db:telemetry-check` to verify required telemetry tables, columns, primary keys, and indexes in the real database.
4. Keep runtime `ensure_telemetry_tables()` as a backward-compatible fallback for existing local environments.
5. Introduce Alembic later only for app-owned schema changes after creating an inventory of current production DB objects.
6. Treat graph preparation as a separate operational migration path because it can be expensive and data-size dependent.
7. Use expand/migrate/contract style for future changes: add nullable columns or new indexes first, backfill separately, switch reads/writes, then remove old objects only after an explicit production plan.

Current non-destructive commands:

```bash
npm run db:telemetry-schema
npm run db:telemetry-check
```

## Auth And Rate Limiting Plan

Current endpoint inventory:

| Endpoint | Current state | Product-safe next step |
| --- | --- | --- |
| `GET /api/health` | Public operational status | Keep public for local/dev. For production, expose deep health only internally or via network policy. |
| `GET /api/metrics` | Public by current project guardrail | Keep contract for now. Add optional token or reverse-proxy protection in a separate product/security change. |
| `GET /api/search` | Public user API | Rate-limit by IP/client at proxy or middleware. Do not require auth for the public map experience without product approval. |
| `GET /api/reverse` | Public user API | Same as search. |
| `GET /api/route` and `GET /route` | Public user API and compatibility alias | Rate-limit by IP/client and protect against abusive coordinate churn. Preserve alias until clients migrate. |
| `POST /api/telemetry/sidewalk-samples` | Public telemetry ingest | Add configurable ingestion limits first. Later require device/project token or signed payload after client rollout. |
| `GET /api/sidewalk-cells` | Public read API for map overlays | Rate-limit by bbox/zoom/client. Keep bbox and resolution validation strict. |
| `GET /tiles/{z}/{x}/{y}.pbf` | Internal map tile endpoint | Add CDN/proxy caching and rate-limit by tile coordinates/client. Auth only if product agrees tiles are not public. |

Rollout sequence:

1. Add config-only limits with defaults that preserve current behavior.
2. Add metrics for would-be throttles before returning `429`.
3. Enforce at the edge proxy first when possible.
4. Add application middleware only after response shape and client handling are agreed.
5. Never log tokens, raw auth headers, or telemetry payload bodies.

## Fresh Bootstrap And Disaster Recovery

Fresh Docker volumes require real data sources:

- `data/osm/moscow-oblast.osm.pbf` for Valhalla.
- `SOURCE_DATABASE_URL` pointing at a database with real `public.moscow_network`.
- PostgreSQL client tools for `psql` and `pg_dump`.

Recommended empty-volume sequence:

```bash
npm run self-hosted:preflight
npm run bootstrap:self-hosted
npm run db:telemetry-check
npm run smoke:self-hosted
```

If `SOURCE_DATABASE_URL` is missing `public.moscow_network`, stop and restore the real safety graph first. Do not create fake rows or a reduced stub graph to satisfy smoke tests.

For current prepared compose volumes, the faster path is:

```bash
npm run self-hosted:up
npm run self-hosted:preflight
npm run smoke:self-hosted
```

## Observability And Robustness

Current strengths:

- Request logging propagates `x-request-id`.
- Dependency HTTP calls propagate the current request ID.
- `/api/health` reports Postgres, Photon, Valhalla, and per-profile readiness.
- Metrics cover HTTP requests, latency, dependency calls, route cache, variants, and failures.
- Database passwords are redacted in health responses.

Recommended next improvements:

- Add structured log events for telemetry ingest failures once auth/rate-limit strategy is decided.
- Add an operational dashboard or scrape target for `/api/metrics`.
- Consider endpoint-specific timeout settings if route and search latency profiles diverge.
- Keep deep health expensive enough to prove readiness, but avoid using it as a high-frequency load balancer probe.

## Test Coverage Gaps

High-value areas to keep expanding:

- Config parsing for production env values.
- Request ID propagation and observability contract.
- PostGIS routing support detection.
- Telemetry schema drift checks against real databases.
- Failure modes for dependency payload shape, bad bbox values, invalid routes, and degraded health.

Avoid brittle tests that assert exact Valhalla geometry or Photon ranking beyond the public contract already smoke-tested with the live stack.

## Performance And DB Safety

Current graph preparation creates:

- GiST index on `moscow_network.geometry`.
- B-tree indexes on `u` and `v`.
- Lowercase highway expression index.
- Profile cost columns.
- Endpoint coordinate columns for A*.
- Materialized `moscow_network_nodes` plus primary key and GiST geometry index.

Do not add new production indexes blindly. For large graph changes, capture `EXPLAIN (ANALYZE, BUFFERS)` with `scripts/profile-safe-route.py`, compare route latency before and after, and apply indexes with a production-safe plan.
