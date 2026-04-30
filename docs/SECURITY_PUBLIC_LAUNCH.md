# Security Public Launch Notes

SafeRoute local/self-hosted defaults stay public and secret-free. Public production deployments should enable edge controls and optional app-level controls before opening expensive or sensitive endpoints.

## Recommended Launch Posture

- Keep `/api/search`, `/api/reverse`, `/api/route`, `/route`, and shallow `/api/health?deep=false` public but edge-rate-limited.
- Protect `/api/metrics`, deep health, telemetry writes, and tiles with deployment config if exposed publicly.
- Use CDN/proxy tile caching and per-IP route/geocode limits.
- Enable app-level API keys as defense in depth where clients can send keys.

## App Env

```bash
PUBLIC_API_KEY_AUTH_ENABLED=true
PUBLIC_API_KEYS=replace-with-real-secret
REQUIRE_API_KEY_FOR_METRICS=true
REQUIRE_API_KEY_FOR_DEEP_HEALTH=true
REQUIRE_API_KEY_FOR_TILES=true
REQUIRE_API_KEY_FOR_TELEMETRY_WRITE=true
RATE_LIMIT_ENABLED=true
TELEMETRY_MAX_BODY_BYTES=262144
```

Do not commit real API keys. Do not log tokens. Rotate keys through deployment secrets.

## Known Limitation

The built-in rate limiter is in-process and fixed-window. It is useful for one-node self-hosted deployments and tests, but public multi-instance deployments need edge/proxy/Redis-backed limits.
