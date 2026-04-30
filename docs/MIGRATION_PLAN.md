# Migration Plan

SafeRoute now has an Alembic baseline for app-owned schema only. Public-launch hardening keeps the current idempotent telemetry schema flow working while adding explicit migration commands for production deployments.

## Current Baseline

The current database lifecycle is split by ownership:

| Asset | Owner | Current mechanism |
| --- | --- | --- |
| PostGIS and pgRouting extensions | platform/runtime | `docker/postgres/init/01_extensions.sql` |
| Telemetry tables and indexes | SafeRoute app | `docker/postgres/init/02_telemetry.sql`, `npm run db:telemetry-schema`, runtime fallback in `ensure_telemetry_tables()`, Alembic baseline |
| Enrichment metadata and per-edge data | SafeRoute app | Alembic baseline, `npm run db:enrichment-check`, `npm run db:enrichment-import` |
| `public.moscow_network` graph | external graph data source | imported from `SOURCE_DATABASE_URL` or restored from a real dump |
| Prepared graph metadata | SafeRoute ops | `scripts/prepare-production-db.sql` |

`public.moscow_network` is not seed data and must not be generated from fake rows. It is operational graph data with a separate bootstrap/recovery process.

## Current Commands

```bash
npm run db:migrate
npm run db:migration-status
npm run db:migration-check
npm run db:telemetry-schema
npm run db:telemetry-check
npm run db:enrichment-check
npm run db:graph-check
```

`npm run db:migrate` applies `0001_app_schema_baseline`, which creates telemetry and enrichment tables/indexes with `IF NOT EXISTS`. It does not drop data and does not manage `public.moscow_network`.

## Recommendation

Alembic is appropriate for app-owned schema changes, especially telemetry and enrichment. It must not replace the graph lifecycle because the graph is large, externally sourced, and operationally restored/imported.

Recommended rollout:

1. Keep the current idempotent SQL baseline for Docker init and local fallback.
2. Run `npm run db:telemetry-schema` before API startup in production-like deployments.
3. Run `npm run db:migrate` to apply app-owned migrations and stamp the Alembic version.
4. Run `npm run db:migration-check`, `npm run db:telemetry-check`, and `npm run db:enrichment-check` as schema drift checks.
5. Run `npm run db:graph-check` as the routing graph readiness check.
6. Keep runtime `ensure_telemetry_tables()` as a backward-compatible local fallback until all deployments run migrations before API startup.

## Rollback Limits

- The Alembic baseline uses additive `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`. Its downgrade is intentionally a no-op to avoid dropping production telemetry or enrichment data.
- Graph prep rebuilds `public.moscow_network_nodes` and updates cost/A* columns. This can be expensive on 1.5M+ edges and should be treated as an operational maintenance action.
- Destructive graph reimport is allowed only when the operator explicitly sets `FORCE_DB_IMPORT=true`; it must be preceded by a real source/dump validation.

## Public-Launch Gate

Before public launch, require all of:

```bash
npm run db:telemetry-schema
npm run db:migrate
npm run db:migration-check
npm run db:telemetry-check
npm run db:enrichment-check
npm run db:graph-check
npm run smoke:self-hosted
```

Alembic is now present for app-owned schema, but graph source reproducibility and security rollout remain separate public-launch gates.
