# SafeRoute Trust Architecture

SafeRoute public beta is a trust-first route decision aid. It compares route options using real routing output and active validated data, but it must never present the result as a guarantee of safety.

## User-Facing Trust Model

The UI separates four concepts:

- **Route score**: a comparative `0..100` score from the backend for the selected route.
- **Data confidence**: frontend-only display metadata derived from active data-source metadata and existing score factors.
- **Route priority**: the user-selected optimization intent such as safer, faster, balanced, or accessible.
- **Unknown risk**: factors that are not active because no verified source is available.

These concepts must not be merged into one “safe” claim. A high score or high data confidence can only mean “better supported by currently available data”.

## Known / Unknown Boundary

“What we know” may use only:

- returned route geometry, time, distance, and maneuvers;
- `score.total`, `score.reasons`, and `score.factors`;
- `score.data_sources.enrichment.active_factors`;
- `score.data_sources.weather` only when the provider is active.

“What we do not know” must stay visible for inactive advanced layers:

- curb risk / curb density;
- official micromobility zones;
- measured traffic;
- pedestrian density;
- telemetry confidence.

Unknown layers are not treated as safe, neutral, or active. They simply do not contribute facts.

## Local Feedback Boundary

The current route feedback UI is a local product note only:

- it is stored only in React component state for the current page session;
- it is not sent to the API;
- it does not create telemetry rows;
- it does not affect route scoring or future recommendations.

Any future submitted feedback requires explicit opt-in, privacy review, storage rules, abuse handling, and documentation before activation.

## Launch Language

Allowed wording:

- “Оценка маршрута по доступным данным.”
- “Не гарантия безопасности.”
- “Часть факторов пока неизвестна.”
- “Отсутствующие слои не подменяются.”

Disallowed wording:

- “Гарантированно безопасно.”
- “Телеметрия активна” when telemetry rows are zero.
- Any claim that curb, measured traffic, pedestrian density, official SIM zones, or telemetry confidence are active without validated real data.
