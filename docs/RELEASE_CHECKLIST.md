# Release Checklist

Use this checklist before a public beta build, demo, or pre-production handoff. It is intentionally stricter than a local UI check and weaker than a safety-grade certification checklist.

## Pre-Release Commands

```bash
npm run build
npm run lint
npm run check:trust-copy
npm run check:release-readiness
npm run typecheck:backend
npm run test:backend
npm run check:backend
npm run check:full
npm run db:enrichment-check
npm run db:enrichment-report
npm run db:telemetry-report
npm run smoke:api
npm run smoke:self-hosted
npm run route:corpus-check
npm run perf:route-smoke
APP_URL=http://127.0.0.1:5173 npm run test:e2e
docker compose ps
```

## Data Gates

- Active enrichment rows must come from validated real datasets.
- `db:telemetry-report` must show whether real telemetry rows exist.
- Curb, official SIM zones, measured traffic, pedestrian density, and telemetry confidence must remain inactive unless their source, checksum, license, mapping, and validation reports pass.
- Optional weather must stay disabled unless `SAFEROUTE_WEATHER_ENABLED=true` is explicitly set.

## Runtime Gates

- Base `docker-compose.yml` must keep `ALLOW_PUBLIC_SERVICE_FALLBACK=false`.
- `/api/health?deep=true` should report primary dependencies as `ok` for production-like local readiness.
- `runtime.readiness=dev_fallback` is acceptable only for local development.
- Map attribution must remain visible.
- Route cards must not show technical source labels or absolute safety guarantees.

## Rollback Note

Prefer code rollback or dataset deactivation. Do not replace failed datasets with synthetic rows, and do not delete Docker volumes unless a separate recovery plan explicitly requires it.
