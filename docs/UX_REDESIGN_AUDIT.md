# SafeRoute UX Redesign Audit

This audit captures the next product direction after the public-beta polish pass. It is implementation-facing: every recommendation must preserve SafeRoute's fail-closed data policy.

## Key Problems

- Safety score can feel like a number instead of a decision aid.
- Reasons need grouping by human concerns: lighting, crossings, surface, calmness, accessibility.
- Search, route selection, and route explanation should feel like one flow.
- Route alternatives need a clear "why this route vs that route" comparison.
- Users need a pre-trip "what to expect" timeline without fake segment-level claims.
- Missing advanced layers should be visible as honest limitations, not warnings.
- Post-trip feedback is absent, but must not become telemetry without opt-in.

## Implemented Direction

- Route details now include a concise explanation, route comparison, data confidence, and "what to expect" timeline derived only from returned score reasons.
- Route cards remain calm and user-facing: no raw Valhalla or dataset labels.
- Local feedback is presented as a product hypothesis only; it is not sent to the server and does not create telemetry rows.
- "О сервисе" explains the product flywheel and privacy boundary in user language.

## Trust v2 Findings

- “Safety score” wording can overpromise if users read it as a real-world guarantee.
- “Confidence” needs to mean confidence in available data coverage, not confidence that the route is safe.
- “What to expect” must be framed as a summary from route reasons and maneuvers, not precise segment-level sensing.
- Feedback must not imply the service is already learning from user reports.

## Trust v2 Changes

- The route detail panel now separates route score, data confidence, route priority, and unknown risk.
- “What we know / what we do not know” makes missing curb, SIM, traffic, pedestrian-density, and telemetry layers explicit.
- Route score copy includes “по доступным данным” and “не гарантия”.
- Local feedback copy states that it stays in the current UI session, is not sent, creates no telemetry, and does not affect routes.
- Absolute labels were softened: the recommended route is no longer named as an absolute safety claim, only as a route with a higher score from available data.
- Technical routing-source labels are kept out of route cards and degraded fallback labels.

## Map-First Home Pass

- The home screen follows the common map-product pattern: full map first, one search bar, and a compact menu.
- The route panel starts closed and opens only after a destination, map point, or menu section is selected.
- The hamburger menu owns secondary sections (`Маршрут`, `Карта`, `О сервисе`) so the first screen is not a dashboard.
- Route/source/trust details remain available after intent, but they do not compete with initial search.

## Design Principles

- Map is the canvas; panels are calm native sheets.
- Route choice comes before data-system detail.
- Confidence is separate from safety.
- Motion explains state changes and respects reduced motion.
- Dark mode tokens must preserve route-line, text, panel, and attribution contrast.

## Research Tasks

- Test whether first-time users understand "Оценка" versus "Уверенность данных".
- Test whether users understand that high data confidence is not a safety guarantee.
- Test whether users can choose between safest and fastest in under 10 seconds.
- Test whether unavailable layers increase trust or anxiety.
- Test whether local feedback copy prevents the impression that telemetry is already collected.
