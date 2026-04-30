# Measured Traffic

Measured traffic is pipeline-ready but inactive. SafeRoute currently has no licensed measured traffic export or API response that can be imported and edge-mapped to `public.moscow_network.id`.

## Current Status

- Status: inactive / pipeline-ready
- Active factor: none
- `avg_traffic_intensity`: must remain `null`
- Score reasons `traffic_intensity` and `low_traffic`: must not appear unless a real active measured source is imported
- Import interface: `npm run db:traffic-import:measured`

## Source Evaluation

| Candidate | Status | Decision |
|---|---|---|
| Moscow Traffic Control Centre / ЦОДД, `https://gucodd.ru/` | Official lead | Not active. No reproducible public edge-level dataset/API export is present. |
| xMap Russia Road Traffic Data | Commercial candidate | Not active without a reviewed license and export file. |
| OSM `highway` / `maxspeed` / `lanes` | Rejected for measured traffic | Legal ODbL graph attributes, but not measured traffic. They remain road-exposure attributes only. |
| Accident / ДТП data | Rejected for measured traffic | May be a future crash-risk layer, but must not be labeled as traffic intensity. |

## Import Contract

The measured traffic importer accepts only real licensed CSV exports. Required operator inputs:

```bash
MEASURED_TRAFFIC_FILE=/path/to/licensed_measured_traffic.csv
DATASET_VERSION=provider-version-or-date
SOURCE_NAME="Provider dataset name"
SOURCE_OWNER="Provider/legal owner"
SOURCE_URL="https://provider/source-or-contract"
SOURCE_LICENSE="License or contract terms"
SOURCE_LICENSE_CONFIRMED=true
SOURCE_CHECKSUM=sha256:<source-file-sha256>
EDGE_MAPPING_METHOD="source edge_id to public.moscow_network.id"
ACTIVATE_ENRICHMENT=true
npm run db:traffic-import:measured
```

CSV rows must include:

- `edge_id`
- `confidence` in `0..1`
- `observed_at` or `time_bucket`
- normalized `traffic_intensity` in `0..1`
- at least one measured raw field: `traffic_volume`, `speed_kmh`, or `congestion_index`

The wrapper validates checksum, provenance, timestamp, measured raw fields, confidence, and factor range before calling the generic enrichment importer. It is idempotent through the existing `safety_edge_enrichment` dataset version flow.

## Rejection Rules

The importer rejects:

- missing provider, owner, license, checksum, dataset version, or edge mapping;
- activation without `SOURCE_LICENSE_CONFIRMED=true`;
- files under `tests/fixtures` when `ACTIVATE_ENRICHMENT=true`;
- OSM road class, `maxspeed`, `lanes`, or road-exposure proxies;
- accident/crash/ДТП sources as measured traffic;
- commercial source metadata without a licensed export file and confirmed license terms.

Launch-safe wording:

> Measured traffic is pipeline-ready but inactive until a real licensed measured traffic source with edge mapping, timestamps, checksum, confidence, and validation is imported.
