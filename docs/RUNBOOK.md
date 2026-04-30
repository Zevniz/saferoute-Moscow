# Incident Runbook

## API Unreachable

1. Check `docker compose ps`.
2. Check API logs with `docker compose logs api --tail=200`.
3. Verify shallow health: `curl http://127.0.0.1:8000/api/health?deep=false`.
4. If DB, Photon, or Valhalla are unhealthy, inspect their logs before restarting API.

## Routes Return 503

1. Run `npm run db:graph-check`.
2. Run `curl http://127.0.0.1:8002/status` for Valhalla.
3. Run `curl 'http://127.0.0.1:2322/api?q=Москва&limit=1'` for Photon.
4. Check API logs for `safe_geometry_algorithm_fallback`, route failures, and dependency errors.

## Missing Graph

1. Run `npm run bootstrap:check`.
2. Provide `SOURCE_DATABASE_URL` or `GRAPH_DUMP_FILE`.
3. Run `npm run db:graph-restore` or `npm run bootstrap:graph`.
4. Run `npm run db:graph-check`.

## Telemetry Issues

1. Run `npm run db:telemetry-schema`.
2. Run `npm run db:telemetry-check`.
3. Check request status codes: `413` means body too large, `422` means validation failed, `503` means DB unavailable.

## Security Controls

If public traffic spikes:

1. Enable edge/proxy limits first.
2. Enable `RATE_LIMIT_ENABLED=true` as local defense in depth.
3. Protect metrics/deep health/telemetry writes with API keys if clients support them.
