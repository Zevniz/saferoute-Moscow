# Data Freshness Policy

SafeRoute public beta depends on OSM-derived and dynamic provider data. Freshness affects trust and must be visible in source metadata and release notes.

## Current Sources

- OSM-derived enrichment: surface, surface quality, sidewalk presence, lighting tags, sparse numeric slope, crossings.
- Optional Open-Meteo weather: dynamic provider, disabled by default.
- Telemetry confidence: inactive because real telemetry tables are empty.

## Freshness Risks

- OSM tags can be stale, incomplete, or locally inconsistent.
- Construction, closures, lighting changes, and crossing changes can happen before the next import.
- Weather can fail or time out; provider failure must remove weather reasons instead of inventing them.
- Missing advanced layers cannot be treated as safe conditions.

## Required Metadata

Every imported dataset should expose:

- source URL/path;
- license;
- checksum;
- version or import date;
- row count and active row count;
- coverage;
- confidence;
- validation result.

## Refresh Practice

- Refresh OSM-derived data before public releases or when source extracts materially change.
- Run enrichment reports after every import.
- Keep raw PBF/data files out of git.
- Update docs when source date, checksum, activation, or validation status changes.

Production-grade launches need a documented refresh cadence, monitoring, and rollback path.
