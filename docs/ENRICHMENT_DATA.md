# Enrichment Data

SafeRoute enrichment uses only real, source-attributed data that is mapped to `public.moscow_network.id` or to OSM way ids already present in that graph. Missing layers stay unavailable: they must not create score penalties, bonuses, reasons, UI claims, or release green checks.

## Active Datasets

| Field | OSM way-tag dataset | OSM crossings dataset |
|---|---|---|
| Dataset version | `osm-moscow-oblast-tags-20260419` | `osm-moscow-oblast-crossings-20260419` |
| Source | OpenStreetMap way tags from Geofabrik Central Federal District extract | OpenStreetMap crossing way tags from Geofabrik Central Federal District extract |
| Source URL | `https://download.geofabrik.de/russia/central-fed-district.html` | `https://download.geofabrik.de/russia/central-fed-district.html` |
| License | ODbL 1.0; attribution required | ODbL 1.0; attribution required |
| Source checksum | `sha256:939e71c748e20c75b020b05fbbddb10f0f627f54daf168210af72056669118da` | `sha256:939e71c748e20c75b020b05fbbddb10f0f627f54daf168210af72056669118da` |
| Generated CSV checksum | Stored in `data/enrichment/osm/moscow-oblast-osm-enrichment.metadata.json` | `sha256:eb5adb84c83f1917d4e0b0ecb8db3ef70be164d00c0889ee9039b0f133ec3931` |
| Mapping | Direct `public.moscow_network.osmid` to OSM way id; no spatial guessing | Direct `public.moscow_network.osmid` to OSM crossing way id; point/node crossings are not guessed |
| Rows imported | `1,126,588` | `62,328` |
| Average confidence | `0.890` | `0.909` |

Official references:

- OpenStreetMap copyright/license: `https://www.openstreetmap.org/copyright`
- Geofabrik Central Federal District extract: `https://download.geofabrik.de/russia/central-fed-district.html`
- OSM kerb docs: `https://wiki.openstreetmap.org/wiki/Key:kerb`
- OSM crossings docs: `https://wiki.openstreetmap.org/wiki/Crossings`
- OSM `footway=crossing`: `https://wiki.openstreetmap.org/wiki/Tag:footway%3Dcrossing`
- OSM pedestrian traffic signals: `https://wiki.openstreetmap.org/wiki/Tag:highway%3Dtraffic_signals`

## Active Factors

| Factor | Rows | Source tag(s) | Notes |
|---|---:|---|---|
| `surface_type` | `1,047,856` | `surface` | Normalized only when values map cleanly to supported SafeRoute enums. |
| `surface_quality` | `101,604` | `smoothness` | Uses OSM smoothness values; unknown values stay blank. |
| `sidewalk_presence` | `12,424` | `sidewalk`, `sidewalk:left`, `sidewalk:right` | Sparse but direct. Partial/conflicting side tags are omitted. |
| `lighting_quality` | `492,436` | `lit` | OSM `lit` tag-derived, not measured illumination. |
| `slope_percent` | `452` | `incline` | Numeric percent only. |
| `crossing_count` | `62,328` | OSM crossing ways | Counts direct crossing ways matched to graph edges by OSM way id. |
| `controlled_crossing_count` | `62,328` | `crossing=traffic_signals`, `crossing=controlled`, `crossing=marked`, `crossing=zebra`, `highway=traffic_signals` | Only tag-derived controlled counts. |
| `uncontrolled_crossing_count` | `62,328` | `crossing=uncontrolled`, `crossing=unmarked`, unknown crossing ways | Unknown direct crossing ways are treated conservatively as uncontrolled/unknown. |
| `crossing_risk` | `62,328` | OSM crossing tags | Higher for uncontrolled/unmarked/unknown, lower for signalized/controlled. |

Conflicting values across multi-way graph edges are omitted per factor. The row can still carry other non-conflicting factors.

## Evaluated But Not Activated

| Factor | Status | Validation result |
|---|---|---|
| `curb_risk`, `curb_frequency`, `curb_density_per_km` | Pipeline-ready, inactive | The expanded OSM curb audit found `104,030` raw curb-like/supporting features and `43,870` normalized real curb/kerb/ramp-to-kerb features. Hybrid mapping produced `1,540` edge rows but only `495` accepted source features, with `29,854` ambiguous features and `98.37%` ambiguity. Validation failed, so curb is not active. |
| `traffic_intensity` | Missing measured source | OSM `maxspeed`/`lanes` remain graph road-exposure attributes, not measured traffic. |
| `pedestrian_density` | Missing source | No legal density source is present. |
| `micromobility_forbidden_zones`, `micromobility_slow_zones` | Missing official zone source | Needs maintained legal polygons with version/checksum. |
| `weather_sensitive_risk` | Optional dynamic provider only | Open-Meteo support is disabled by default; it affects scoring only when `SAFEROUTE_WEATHER_ENABLED=true` and a real provider response succeeds. |
| `telemetry_confidence` | Missing data | Telemetry schema exists, but `sidewalk_samples` and `sidewalk_cell_aggregates` are currently empty. |

## Commands

Build/import active OSM way-tag enrichment:

```bash
ACTIVATE_ENRICHMENT=true npm run db:enrichment-import:osm
```

Build/import validated OSM crossing enrichment:

```bash
npm run db:enrichment-import:crossings-osm
```

Attempt curb enrichment, activation-gated by validation:

```bash
npm run db:enrichment-import:curb-osm
```

The curb importer writes an ignored metadata report to `data/enrichment/osm/moscow-oblast-osm-curb.metadata.json`. The latest validation result is intentionally inactive:

- source checksum: `sha256:939e71c748e20c75b020b05fbbddb10f0f627f54daf168210af72056669118da`;
- generated CSV checksum: `sha256:86dd0aa235fae988ce88533036f5428a8cc391e7143bf647f162c555c07f1703`;
- accepted features: `495` / required `1,000`;
- imported candidate edge rows: `1,540` / required `1,000`;
- ambiguous features: `29,854`;
- ambiguous rate: `0.9837` / maximum `0.15`;
- median distance: `0.0m`;
- p95 distance: `2.753m`;
- plausible edge rate: `1.0`;
- incompatible edge rate: `0.0`.

This means the distance and edge-class gates pass, but coverage and ambiguity do not. Do not activate curb from this OSM extract without a stronger edge mapping source.

Check/report:

```bash
npm run db:enrichment-check
npm run db:enrichment-report
```

Generated CSV and metadata live under `data/enrichment/`, which is ignored by git. Do not commit raw/generated enrichment datasets.

## API Behavior

Route score payloads include additive source metadata. With both active OSM datasets:

```json
{
  "score": {
    "data_sources": {
      "enrichment": {
        "active": true,
        "active_factors": [
          "controlled_crossing_count",
          "crossing_count",
          "crossing_risk",
          "lighting_quality",
          "sidewalk_presence",
          "slope_percent",
          "surface_quality",
          "surface_type",
          "uncontrolled_crossing_count"
        ],
        "dataset_versions": [
          "osm-moscow-oblast-crossings-20260419",
          "osm-moscow-oblast-tags-20260419"
        ]
      }
    }
  }
}
```

If no active dataset exists, `data_sources.enrichment.active` is `false`, and optional enrichment factors remain `null`/unavailable.
