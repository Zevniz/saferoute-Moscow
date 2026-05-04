# Privacy And Telemetry

SafeRoute public beta is privacy-first by default. Route planning does not create telemetry rows, and the current route-feedback UI is a local session note only.

## Current Behavior

- Route search and routing use request coordinates to answer the current request.
- The "Заметка о маршруте" control stores only local UI state in the browser session.
- Feedback clicks do not call `fetch`, `XMLHttpRequest`, the telemetry API, or any analytics endpoint.
- The verified self-hosted telemetry tables currently contain `0` rows in `sidewalk_samples` and `0` rows in `sidewalk_cell_aggregates`.
- `avg_telemetry_confidence` remains `null` until real observations exist.

## Operational Observability Is Not Telemetry

The backend records operational counters and JSON log events for service health and debugging:

- request id, method, low-cardinality path, status, and duration;
- dependency status and latency;
- route API outcome by profile and mode;
- safe-geometry fallback reason.

These logs intentionally do not include full route URLs, route coordinate query strings, search text, route history, local feedback, or personal movement history.

## What Feedback Does Not Do

- It does not train route scoring.
- It does not create H3 cells.
- It does not write `sidewalk_samples`.
- It does not imply that SafeRoute is learning from the user.
- It does not activate telemetry confidence.

## Future Opt-In Telemetry Gate

Before any submitted feedback or telemetry can affect routing, the implementation must add:

- explicit user opt-in;
- clear retention and deletion rules;
- abuse/spam handling;
- privacy aggregation thresholds;
- source quality and recency scoring;
- docs update and tests proving rows are real, not generated.

Until those gates exist, UI copy must say that route notes stay in the current interface session and do not affect routes.
