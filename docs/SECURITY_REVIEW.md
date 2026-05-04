# Security Review

This is a lightweight public-beta security review for the current SafeRoute stack.

## Current Protections

- Route coordinates use FastAPI numeric bounds.
- Routing profile and route mode are allowlisted.
- Search query length is bounded before Photon is called.
- Telemetry batch size and body size are bounded by config.
- CORS origins are explicit and configurable.
- Optional API-key protection exists for public API, metrics, deep health, tiles, and telemetry writes.
- Optional rate limiting exists per route class.
- Request logs use low-cardinality paths and do not include coordinate query strings.
- Database passwords are redacted in health responses.
- Base Docker Compose keeps public Photon/Valhalla fallback disabled.

## Remaining Risks

- Public beta defaults do not force API keys or rate limits in every local runtime.
- No centralized WAF or managed bot protection is configured in repo.
- Metrics endpoint can be public unless operators require an API key.
- Vector tile access can be public unless operators enable tile API-key protection.
- Route/search endpoints can be expensive under abuse without rate limits.
- Full production secret management is outside this repository.

## Recommended Next Steps

- Enable API keys and rate limits for public deployments.
- Protect deep health and metrics outside trusted networks.
- Add production monitoring and alerting for 5xx, latency, dependency fallback, and route failure counters.
- Run dependency audit in CI.
- Keep full route coordinates out of logs and analytics.
- Add a formal incident review for any safety, scoring, privacy, or attribution regression.
