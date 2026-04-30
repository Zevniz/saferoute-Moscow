# Pedestrian Density

Pedestrian density is pipeline-ready but inactive. SafeRoute currently has no licensed measured pedestrian count, flow, density, or heatmap export that can be imported and mapped to the Moscow route graph.

## Current Status

- Status: inactive / pipeline-ready
- Active factor: none
- `avg_pedestrian_density`: must remain `null`
- Score reason `high_pedestrian_density`: must not appear unless a real active measured source is imported
- Import interface: `npm run db:pedestrian-import:density`

## Source Evaluation

| Candidate | Status | Decision |
|---|---|---|
| Moscow pedestrian/bicycle master planning project | Lead only | Not active. Project page is evidence that analysis existed, not a reproducible dataset/export. |
| SmartLoc pedestrian heatmaps Moscow | Commercial candidate | Not active without reviewed license terms and a source export. |
| POI density / transit stops / land-use | Rejected for measured density | These may become a separately labeled proxy, but must not be called measured pedestrian density. |

## Import Contract

The pedestrian-density importer accepts only real licensed CSV exports. Required operator inputs:

```bash
PEDESTRIAN_DENSITY_FILE=/path/to/licensed_pedestrian_density.csv
DATASET_VERSION=provider-version-or-date
SOURCE_NAME="Provider dataset name"
SOURCE_OWNER="Provider/legal owner"
SOURCE_URL="https://provider/source-or-contract"
SOURCE_LICENSE="License or contract terms"
SOURCE_LICENSE_CONFIRMED=true
SOURCE_CHECKSUM=sha256:<source-file-sha256>
EDGE_MAPPING_METHOD="source edge_id to public.moscow_network.id"
ACTIVATE_ENRICHMENT=true
npm run db:pedestrian-import:density
```

CSV rows must include:

- `edge_id`
- `confidence` in `0..1`
- `observed_at` or `time_bucket`
- normalized `pedestrian_density` in `0..1`
- at least one measured raw field: `pedestrian_count`, `pedestrian_flow`, or `density_value`

## Privacy And Licensing

Pedestrian density can be sensitive. A production source must include license/terms, aggregation level, privacy review, timestamp/time bucket, confidence, update cadence, and an audited mapping method to `public.moscow_network.id` or graph-intersecting cells/polygons converted to edge rows.

## Rejection Rules

The importer rejects:

- missing provider, owner, license, checksum, dataset version, or edge mapping;
- activation without `SOURCE_LICENSE_CONFIRMED=true`;
- files under `tests/fixtures` when `ACTIVATE_ENRICHMENT=true`;
- POI, transit, station, land-use, or generic proxy inputs as measured pedestrian density;
- commercial source metadata without a licensed export file and confirmed license terms.

Launch-safe wording:

> Pedestrian density is pipeline-ready but inactive until a real licensed measured pedestrian-density source with privacy review, edge mapping, timestamps, checksum, confidence, and validation is imported.
