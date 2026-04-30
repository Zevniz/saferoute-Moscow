# Data Attribution

SafeRoute public beta uses OpenStreetMap-derived graph and enrichment data and a CARTO basemap style. Attribution must remain visible in public builds and release materials.

## OpenStreetMap

Display this attribution in the map UI:

```text
© OpenStreetMap contributors
```

Link it to:

```text
https://www.openstreetmap.org/copyright
```

OpenStreetMap data is used for the Moscow routing graph and for active enrichment datasets `osm-moscow-oblast-tags-20260419` and `osm-moscow-oblast-crossings-20260419`.

## Geofabrik Extract

The active OSM-derived enrichment source is the Geofabrik Central Federal District extract:

```text
https://download.geofabrik.de/russia/central-fed-district.html
```

SafeRoute imports only real OSM way/crossing tags that can be joined to `public.moscow_network.osmid`. The import does not create synthetic surface, sidewalk, lighting, slope, curb, traffic, pedestrian, micromobility, weather, or telemetry-confidence values.

## CARTO

The frontend uses a CARTO basemap style. Display visible CARTO attribution and link it to:

```text
https://carto.com/attributions
```

## ODbL Notes

OpenStreetMap data is distributed under the Open Database License. Public SafeRoute builds and artifacts should preserve attribution and document that OSM-derived graph/enrichment data may carry ODbL obligations.

This document is an engineering attribution checklist, not legal advice. Review ODbL obligations before distributing derived graph dumps, enrichment CSVs, hosted tiles, or offline data packages.

## Open-Meteo

If `SAFEROUTE_WEATHER_ENABLED=true` is used in a public build, the UI or release notes must include Open-Meteo attribution and link to:

```text
https://open-meteo.com/en/docs
https://open-meteo.com/en/licence
```

Open-Meteo API data is offered under CC BY 4.0. The UI badge should only appear when real weather data is displayed.

Weather is not fetched or displayed in the default public beta runtime.

## UI Requirement

The map UI must keep both attribution links visible:

- `© OpenStreetMap contributors`
- `CARTO`

Do not hide attribution behind a debug panel, settings panel, hover-only tooltip, or authenticated-only surface.
