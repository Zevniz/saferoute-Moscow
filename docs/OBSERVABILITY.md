# Observability

SafeRoute observability is operational. It is not user telemetry and must not store route history or personal location history.

## What Is Observed

- HTTP method, low-cardinality route path, response status, duration, and request id.
- Dependency request counts and latency for Photon, Valhalla, weather provider, and route internals.
- Route API outcome counts by profile and mode, without coordinates.
- Safe-geometry bounded/full/fallback duration and fallback reason.
- Route cache hit/miss/expired counters.
- Health state for Postgres, Photon, Valhalla, and per-profile route readiness.

## What Is Not Observed

- Full request URLs with route coordinates.
- Search query bodies in logs.
- User route history.
- Local feedback clicks.
- Raw telemetry unless a user or device explicitly posts to the telemetry API under the documented telemetry contract.

## Health States

- `status=ok`: checked dependencies and profiles are healthy.
- `status=degraded`: one or more checked dependency/profile states are not fully healthy.
- dependency `status=fallback`: a public fallback dependency served a check; this is local-dev-only.
- `runtime.readiness=self_hosted_ready`: all checked dependencies are primary self-hosted services and public fallback is disabled.
- `runtime.readiness=local_dev_ready`: dependencies are healthy but public fallback is enabled.
- `runtime.readiness=dev_fallback`: at least one dependency used public fallback.

## Debugging Degraded Routing

1. Check `GET /api/health?deep=true`.
2. Check `GET /api/metrics` for dependency and route failure counters.
3. Run `npm run smoke:self-hosted`.
4. Inspect container logs for Postgres, Photon, Valhalla, and API.
5. If route scoring is degraded, run `npm run db:enrichment-report` and `npm run db:telemetry-report`.

Do not treat fallback as production readiness.
