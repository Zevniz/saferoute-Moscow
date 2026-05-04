# Scoring Governance

SafeRoute scoring is allowed to guide route choice, but it must not create facts that data does not support.

## Concepts

- Route score: a weighted score from available route factors.
- Data confidence: an estimate of available data coverage and completeness.
- Route preference: the selected optimization mode, such as calmer, faster, balanced, or accessible.
- Unknown risk: factors that are not covered by active datasets.

These concepts must remain separate in API, UI, docs, and tests.

## Adding Or Changing A Factor

Every scoring factor needs:

- real source or provider;
- source owner and license;
- checksum/version/date where applicable;
- import and validation command;
- mapping method;
- coverage and confidence report;
- tests proving missing data does not create a value or reason;
- docs update in `SCORING_FACTORS.md`.

## Disallowed Scoring Behavior

- Treating missing data as safe.
- Reusing import confidence as telemetry confidence.
- Calling OSM road class, lanes, or maxspeed "measured traffic".
- Calling POI density or transit access "measured pedestrian density".
- Activating curb/SIM/traffic/pedestrian/telemetry without a validated source.
- Adding AI-generated route facts that do not come from route response fields.

## Copy Rules

Use qualified wording:

- "по доступным данным"
- "не гарантия"
- "часть факторов пока неизвестна"

Avoid absolute claims:

- "гарантированно безопасно"
- "самый безопасный маршрут"
- "данные точные"
- "можно доверять полностью"

`npm run check:trust-copy` enforces the most important public-copy guardrails in `src/` and `app/`.
