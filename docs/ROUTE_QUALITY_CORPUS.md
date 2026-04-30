# Route Quality Corpus

`npm run route:corpus-check` verifies a small real-route corpus against a running API. It is not a fake test and does not mock Photon, Valhalla, or PostGIS.

## What It Checks

- all modes: `safest`, `fastest`, `balanced`, `accessible`;
- profiles across walk, bike, and car;
- route count is between 1 and 3;
- geometry is a real `LineString`;
- score is bounded `0..100`;
- `safety_index` remains an integer;
- score reasons are machine-readable;
- enrichment source metadata is allowed and should remain honest: active OSM surface/sidewalk/lighting/slope/crossing factors may appear, unavailable curb/measured-traffic/pedestrian/micromobility/default-weather/telemetry factors must not be required;
- no route request returns 500.

The script avoids exact geometry or score snapshots because Valhalla alternatives and graph prep can change valid route choices.

## Run

```bash
npm run self-hosted:up
npm run smoke:self-hosted
npm run route:corpus-check
```

Use `API_URL=http://host:port` to target another API instance.
