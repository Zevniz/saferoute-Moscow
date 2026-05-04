# Incident Response

This runbook covers routing, scoring, privacy, and data-attribution incidents for SafeRoute public beta.

## Incident Types

- Routing outage: API, Photon, Valhalla, PostGIS, or pgRouting unavailable.
- Scoring incident: scores or reasons are missing, misleading, or fabricated.
- Data incident: stale, corrupt, unlicensed, or wrongly activated enrichment dataset.
- Privacy incident: unexpected telemetry write, feedback submission, or sensitive logging.
- Attribution incident: OSM/CARTO/Open-Meteo attribution hidden or incorrect.

## Immediate Actions

1. Stop promoting the affected feature as active.
2. Check `/api/health?deep=true`, container logs, and recent deploy/import changes.
3. Run the smallest relevant verification command:
   - `npm run smoke:api`
   - `npm run smoke:self-hosted`
   - `npm run db:enrichment-report`
   - `npm run db:telemetry-report`
   - `npm run check:trust-copy`
   - `npm run check:release-readiness`
4. If a dataset is suspect, deactivate it through normal non-destructive dataset activation controls. Do not delete Docker volumes as a first response.
5. Communicate degraded behavior as "данные временно недоступны", not as a safety guarantee.

## Health Interpretation

- `runtime.readiness=self_hosted_ready`: production-like local dependencies are primary and healthy.
- `runtime.readiness=local_dev_ready`: dependencies are healthy, but public fallback is enabled and the runtime is not production-like.
- `runtime.readiness=dev_fallback`: a public fallback is serving checks; treat as degraded and local-dev-only.
- `runtime.readiness=degraded`: a dependency or route profile is unavailable.

## Rollback Guidance

- Prefer code rollback or dataset deactivation over destructive DB operations.
- Never replace a failed dataset with synthetic rows.
- Keep raw import artifacts out of git and preserve checksums for investigation.
- If telemetry rows appear unexpectedly, stop write paths and inspect API logs before running further imports.

## Post-Incident Review

Document:

- user-visible impact;
- affected route factors;
- source/version/checksum;
- verification command results;
- prevention test or alert added.
