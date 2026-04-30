# Weather Risk

Weather risk is dynamic route context, not a static graph enrichment dataset.

## Status

- Default runtime: inactive
- Optional provider: Open-Meteo
- Enable with: `SAFEROUTE_WEATHER_ENABLED=true`
- Provider env: `SAFEROUTE_WEATHER_PROVIDER=open_meteo`
- Backward-compatible provider alias: `open-meteo`
- Cache TTL env: `SAFEROUTE_WEATHER_CACHE_TTL_SECONDS=900`
- Timeout env: `SAFEROUTE_WEATHER_TIMEOUT_SECONDS=3.0`
- API key: not used by the default Open-Meteo configuration

## Source

- API docs: `https://open-meteo.com/en/docs`
- License/terms: `https://open-meteo.com/en/licence`
- API data license: CC BY 4.0; public displays must attribute and link to Open-Meteo.

SafeRoute fetches current weather at the route geometry bounding-box centroid only when weather is enabled. It requests `temperature_2m`, `precipitation`, `rain`, `snowfall`, `weather_code`, `wind_gusts_10m`, and `visibility` from Open-Meteo current conditions.

## Scoring Behavior

`weather_sensitive_risk` affects scoring only when:

1. `SAFEROUTE_WEATHER_ENABLED=true`;
2. provider is `open_meteo`;
3. the request succeeds;
4. current weather payload contains usable real values.

Risk is normalized to `0..1` and weighted by provider confidence. The current Open-Meteo integration sets confidence to `1.0` only after a valid provider response. Benign weather can produce active source metadata with `risk=0` and no penalty reason.

If the provider fails, times out, or returns invalid data, SafeRoute adds no weather reason and leaves weather risk unavailable for that route. It does not infer weather from static graph data.

## UI And API

When active for a route, score metadata may include:

```json
{
  "data_sources": {
    "weather": {
      "active": true,
      "provider": "open_meteo",
      "provider_label": "Open-Meteo",
      "source_url": "https://open-meteo.com/en/docs",
      "attribution": "Weather data by Open-Meteo.com",
      "license": "CC BY 4.0",
      "license_url": "https://open-meteo.com/en/licence",
      "sample_method": "route_bbox_centroid",
      "cache_ttl_seconds": 900,
      "timeout_seconds": 3.0,
      "confidence": 1.0,
      "risk": 0.42
    }
  }
}
```

The UI must show Open-Meteo attribution only when weather data is displayed. Default public-beta runtime does not display weather attribution because weather is disabled.

## Limitations

- Local weather at the route bbox centroid is an approximation; it is not edge-specific.
- Weather risk is not a substitute for measured surface, curb, traffic, or telemetry data.
- Do not cache weather longer than the configured TTL for public claims.
