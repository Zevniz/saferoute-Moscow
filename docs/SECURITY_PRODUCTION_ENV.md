# Production Security Env

Local self-hosted defaults remain no-auth and no-rate-limit compatible. Production can fail closed with API keys, rate limits, body limits, and protected diagnostics through env.

## Env Aliases

Canonical repo envs remain supported. `SAFEROUTE_*` aliases are additive:

| Preferred env | Existing env | Behavior |
| --- | --- | --- |
| `SAFEROUTE_ENV` | `ENVIRONMENT` | Runtime environment. Use `production` for public deployments. |
| `SAFEROUTE_REQUIRE_API_KEY` | per-endpoint `REQUIRE_API_KEY_FOR_*` | When true, protects route/search/reverse/metrics/deep health/tiles/telemetry writes. |
| `SAFEROUTE_API_KEYS` | `PUBLIC_API_KEYS` | Comma-separated or JSON-array API keys. |
| `SAFEROUTE_RATE_LIMIT_ENABLED` | `RATE_LIMIT_ENABLED` | Enables in-process fixed-window limits. |
| `SAFEROUTE_RATE_LIMIT_PER_MINUTE` | `RATE_LIMIT_*_PER_WINDOW` | Sets all bucket defaults unless a specific bucket env is set. |
| `SAFEROUTE_MAX_TELEMETRY_PAYLOAD_BYTES` | `TELEMETRY_MAX_BODY_BYTES` | Rejects oversized telemetry writes. |
| `SAFEROUTE_PROTECT_DEEP_HEALTH` | `REQUIRE_API_KEY_FOR_DEEP_HEALTH` | Protects `/api/health?deep=true`. |

`/api/health?deep=false` remains public so load balancers can perform shallow health checks.

## Local Defaults

```bash
ENVIRONMENT=local
PUBLIC_API_KEY_AUTH_ENABLED=false
RATE_LIMIT_ENABLED=false
```

This keeps existing local browser, smoke, and self-hosted workflows compatible.

## Production Example

Use `.env.production.example` as the non-secret template. Replace API keys and database credentials in the deployment secret manager, not in git.

```bash
SAFEROUTE_ENV=production
SAFEROUTE_REQUIRE_API_KEY=true
SAFEROUTE_API_KEYS=replace-with-generated-key-1,replace-with-generated-key-2
SAFEROUTE_RATE_LIMIT_ENABLED=true
SAFEROUTE_RATE_LIMIT_PER_MINUTE=120
SAFEROUTE_MAX_TELEMETRY_PAYLOAD_BYTES=262144
SAFEROUTE_PROTECT_DEEP_HEALTH=true
```

Specific buckets can override the generic limit:

```bash
RATE_LIMIT_ROUTE_PER_WINDOW=60
RATE_LIMIT_GEOCODE_PER_WINDOW=120
RATE_LIMIT_TELEMETRY_PER_WINDOW=30
RATE_LIMIT_TILES_PER_WINDOW=600
RATE_LIMIT_METRICS_PER_WINDOW=30
RATE_LIMIT_HEALTH_PER_WINDOW=120
```

## API Key Usage

Clients may send either:

```http
Authorization: Bearer <key>
```

or:

```http
x-saferoute-api-key: <key>
```

The API compares keys in constant time and does not log tokens. Rate-limit identity hashes API keys before storing in the in-process counter.

## Protected Surface

When `SAFEROUTE_REQUIRE_API_KEY=true`, these endpoint groups require a valid key:

- `/api/search`
- `/api/reverse`
- `/api/route`
- `/route`
- `/api/metrics`
- `/api/health?deep=true`
- `/tiles/{z}/{x}/{y}.pbf`
- `/api/telemetry/sidewalk-samples`
- `/api/sidewalk-cells`

Telemetry writes also enforce `SAFEROUTE_MAX_TELEMETRY_PAYLOAD_BYTES`.

## Operational Notes

The built-in rate limiter is per process and suitable as an application backstop. Public deployments should still use an edge proxy or ingress rate limit for distributed enforcement.

If API-key protection is enabled with no configured keys, protected endpoints return `503` instead of silently becoming public.

## Local Production-Mode Verification

For a local production-security probe, start an API instance with a dummy key and a low rate limit:

```bash
SAFEROUTE_ENV=production \
SAFEROUTE_REQUIRE_API_KEY=true \
SAFEROUTE_API_KEYS=local-test-key \
SAFEROUTE_RATE_LIMIT_ENABLED=true \
SAFEROUTE_RATE_LIMIT_PER_MINUTE=2 \
SAFEROUTE_PROTECT_DEEP_HEALTH=true \
SAFEROUTE_MAX_TELEMETRY_PAYLOAD_BYTES=262144 \
DATABASE_URL=postgresql://saferoute:saferoute_pass@127.0.0.1:5434/saferoute_db \
PHOTON_URL=http://127.0.0.1:2322 \
VALHALLA_URL=http://127.0.0.1:8002 \
./venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 18080
```

Then run:

```bash
API_URL=http://127.0.0.1:18080 \
SAFEROUTE_API_KEY=local-test-key \
SECURITY_EXPECT_RATE_LIMIT=true \
SECURITY_RATE_LIMIT_PROBE_COUNT=4 \
npm run security:production-check
```

The probe checks:

- shallow health is public;
- deep health without key is rejected;
- route without key is rejected;
- route with key is accepted;
- rate limit returns `429`.

The probe sends the key in request headers but never prints it.
