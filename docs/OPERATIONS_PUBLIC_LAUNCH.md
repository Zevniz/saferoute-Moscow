# Public Launch Operations

## Startup Order

```bash
docker compose build api
docker compose build frontend
npm run self-hosted:preflight
npm run self-hosted:up
npm run db:telemetry-schema
npm run db:migrate
npm run db:migration-check
npm run db:telemetry-check
npm run db:enrichment-check
npm run db:graph-check
npm run bootstrap:check
npm run smoke:self-hosted
npm run route:corpus-check
```

For a fresh machine or disaster-recovery rehearsal, run the isolated bootstrap before exposing the service:

```bash
npm run bootstrap:fresh
```

This uses a separate compose project and volumes. It must restore a real graph from `GRAPH_DUMP_FILE` or import from a real `SOURCE_DATABASE_URL`; it must not be replaced by sample graph data.

## Readiness Signals

- `GET /api/health?deep=false`: API and core dependencies for load balancers.
- `GET /api/health?deep=true`: dependency and profile readiness; protect or keep internal in production.
- `npm run db:graph-check`: graph data and prepared routing metadata.
- `npm run db:telemetry-check`: telemetry schema drift.
- `npm run db:migration-check`: app-owned migration head.

## Performance Smokes

```bash
npm run perf:route-smoke
npm run perf:telemetry-smoke
```

These are local sanity checks, not public SLA guarantees.

## Public Launch Blockers

SafeRoute is not fully public-launch ready until the deployment has:

- a reproducible real graph source or dump published for the deployment, with checksum/manifest;
- an explicit auth/rate-limit deployment policy enabled in the production edge/app config;
- real enrichment data source, or a product-approved launch posture that clearly marks advanced factors inactive;
- backup/restore playbook tested on the target environment.

The local self-hosted MVP and isolated fresh bootstrap path are verified. Public launch still requires the deployment owner to publish the graph artifact/source and enable the documented security policy in the target environment.
