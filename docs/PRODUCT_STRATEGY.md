# SafeRoute Product Strategy

SafeRoute is positioned as a calm, explainable safety navigator for Moscow. It should not compete with generic map products on breadth alone; it should win trust by showing why one route is calmer, what data supports that judgement, and which safety layers are still unavailable.

## Positioning

- Primary promise: safer and more comfortable urban routing, with honest data confidence.
- Initial ICP: pedestrians, micromobility riders, parents, night commuters, accessibility-sensitive users, couriers, campuses, and city partners.
- Core job: "Get me there without unpleasant surprises, and explain the tradeoff."
- North-star metric: verified safe trips completed per weekly active user.
- Guardrail metric: fake active safety-layer claims must remain zero.

## Product Flywheel

1. Real graph routes and verified OSM enrichment create baseline trust.
2. Clear explanations increase route starts and feedback.
3. Opt-in, privacy-reviewed observations improve confidence coverage.
4. Better confidence improves route choice and explanation quality.
5. Better outcomes create more repeat usage and more verified observations.

## Growth Loops

- Shared safe route: recipient opens a route, sees safety explanation, and can try SafeRoute.
- Saved commute: users return when the route changes because weather or verified data changes.
- Data coverage transparency: public provenance pages turn limitations into trust.
- Partner loop: campuses/couriers/cities contribute licensed data and receive safer route analytics.

## Monetization Paths

- Free public beta for consumer trust and coverage.
- Premium saved routes, offline packs, route monitoring, and weather-aware alerts.
- B2B safe-route scoring API for couriers and mobility operators.
- City/campus safety analytics based only on licensed or opt-in aggregated data.

## Roadmap Principles

- AI explanations may use only active real factors and route metadata.
- Missing data must stay absent/null, never inferred as safe.
- Telemetry requires explicit opt-in, aggregation thresholds, and privacy review.
- Measured traffic and pedestrian density require licensed measured exports, not proxies.
- Every new factor must pass the scoring-governance gate before it can affect route choice.
- Public beta positioning is trust-first: limitations should be visible, short, and useful.

## Trust v2

- Route score, data confidence, route priority, and unknown risk are separate product concepts.
- The UI must say “по доступным данным” and “не гарантия” near route explanations, not only in docs.
- Local route feedback is a session-only note until a future opt-in feedback system exists.
- The product should earn trust by showing what is unknown instead of hiding inactive safety layers.

## vNext Product Risks

- Users may still overread a high route score as a real-world guarantee. Keep "по доступным данным" close to the score.
- Route confidence can be confused with safety. Keep confidence language tied to data coverage, not personal safety.
- Feedback can create an expectation of learning. Keep the current session-only boundary until opt-in telemetry exists.
