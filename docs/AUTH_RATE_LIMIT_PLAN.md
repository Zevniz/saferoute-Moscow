# Auth And Rate-Limit Rollout Plan

This plan documents the product-safe public-launch path. The app now includes optional API-key and in-process rate-limit enforcement, disabled by default so existing local clients and smoke checks remain compatible.

## Endpoint Decisions

| Endpoint | Launch posture | Reason |
| --- | --- | --- |
| `GET /api/search` | Public, rate-limited at edge/proxy | Core map search UX. |
| `GET /api/reverse` | Public, rate-limited at edge/proxy | Core map/reverse UX. |
| `GET /api/route` | Public, rate-limited at edge/proxy | Core routing UX; expensive enough to monitor closely. |
| `GET /route` | Public compatibility alias, rate-limited at edge/proxy | Preserve existing clients while migrating to `/api/route`. |
| `GET /api/health?deep=false` | Public or load-balancer visible | Shallow health is useful for readiness and local operations. |
| `GET /api/health?deep=true` | Prefer internal/protected in production | Deep health calls real dependencies and route readiness. |
| `GET /api/metrics` | Protect with network policy, reverse proxy auth, or optional token in a future app change | Metrics can expose operational shape and traffic volume. |
| `POST /api/telemetry/sidewalk-samples` | Public for local MVP; move to optional device/API key before public ingest | Write endpoint can be abused and should identify trusted devices. |
| `GET /api/sidewalk-cells` | Public read API, rate-limited by bbox/client | Map overlay read path; validation already bounds bbox/resolution. |
| `GET /tiles/{z}/{x}/{y}.pbf` | Public or CDN-backed if tiles are part of product; otherwise proxy-protected | Tile reads can be high-volume and should be cached/rate-limited. |

## Backwards-Compatible Rollout

1. Start with edge/proxy limits and observe-only app metrics.
2. Keep local self-hosted defaults public and secret-free.
3. Enable optional application API-key support only after product approves client rollout.
4. When optional keys exist, accept both unauthenticated and authenticated traffic during migration.
5. Enforce keys only after client adoption and incident playbooks are ready.

## App-Level Configuration

Local defaults leave all endpoints public:

```bash
PUBLIC_API_KEY_AUTH_ENABLED=false
RATE_LIMIT_ENABLED=false
```

Production can opt in without changing public API response contracts:

```bash
PUBLIC_API_KEY_AUTH_ENABLED=true
PUBLIC_API_KEYS=key-one,key-two
REQUIRE_API_KEY_FOR_METRICS=true
REQUIRE_API_KEY_FOR_DEEP_HEALTH=true
REQUIRE_API_KEY_FOR_TILES=true
REQUIRE_API_KEY_FOR_TELEMETRY_WRITE=true
RATE_LIMIT_ENABLED=true
RATE_LIMIT_ROUTE_PER_WINDOW=60
RATE_LIMIT_GEOCODE_PER_WINDOW=120
RATE_LIMIT_TELEMETRY_PER_WINDOW=60
RATE_LIMIT_TILES_PER_WINDOW=600
RATE_LIMIT_METRICS_PER_WINDOW=60
RATE_LIMIT_HEALTH_PER_WINDOW=120
```

The in-process limiter is a defense-in-depth fallback. Multi-instance public deployments still need edge/CDN/proxy limits because each API worker has its own local counter.

## Proposed Limits

Initial edge/proxy defaults:

- search/reverse: moderate per-IP request rate, short burst allowance;
- route: lower per-IP request rate due to PostGIS/Valhalla cost;
- telemetry ingest: strict body size and batch-size limits plus per-device/project limits once identity exists;
- tiles: CDN cache first, rate-limit by IP and tile coordinate churn;
- metrics/deep health: internal network or explicit token.

The app already enforces several non-breaking limits:

- `search.limit <= 8`;
- `route.alternatives <= 3`;
- route coordinates are bounded latitude/longitude values;
- tile `z/x/y` coordinates are bounded before database access;
- telemetry sample batch has Pydantic max length, runtime `TELEMETRY_MAX_BATCH_SIZE`, and optional `TELEMETRY_MAX_BODY_BYTES`;
- telemetry coordinates are constrained to the Moscow/Moscow-oblast product area;
- sidewalk-cell bbox and H3 resolution are validated before database access.

## API Key Strategy

Current optional app-level auth accepts:

- `Authorization: Bearer <token>` or `X-SafeRoute-Api-Key`;
- comma-separated or JSON-array `PUBLIC_API_KEYS`;
- safe logs that never include raw token values.

Future persisted auth should use hashed tokens at rest and token labels/scopes such as `telemetry:write`, `metrics:read`, and `tiles:read`.

Do not require tokens by default in local self-hosted mode.

## Abuse Cases

- route coordinate churn causing expensive graph/Valhalla requests;
- telemetry write floods or poisoned device data;
- tile scraping without CDN cache;
- metrics scraping by untrusted clients;
- deep health polling too frequently;
- search spam against Photon.

## Public-Launch Gate

SafeRoute is not public-launch ready until product/security deploys one of:

- edge-only enforcement with documented proxy config and monitoring, or
- optional app-level API keys plus edge limits with a backwards-compatible migration window, or
- mandatory auth for selected endpoints with a client rollout plan.

The app implementation exists, but deployment policy must still be explicitly chosen and enabled for a public launch.
