# SafeRoute Explainability Model

SafeRoute explanations are deterministic UI summaries of existing route data. They are not AI-generated facts and do not infer missing safety layers.

## Inputs

Explanations may use:

- route label, subtitle, geometry, distance, time, calories, and maneuvers;
- `properties.score.total`;
- `properties.score.reasons[]`;
- `properties.score.data_sources`;
- the set of returned alternatives for score/time/distance comparison.

Explanations must not use:

- generated telemetry;
- inferred curb, traffic, pedestrian-density, or micromobility-zone facts;
- private user traits;
- source leads without imported, validated data.

## Route Explanation Structure

The “Why this route” panel follows this order:

1. Main reason from returned score reasons.
2. Comparison with alternatives using score/time/distance only.
3. Tradeoff or limitation copy.
4. Data confidence and unknown risk.
5. “What we know / what we do not know.”
6. Short route timeline derived from maneuvers and score reasons.

The timeline is a pre-trip summary. It must not imply precise segment-level coverage unless the API returns segment-level facts.

## Data Confidence

Data confidence is display-only. It helps users understand how much active metadata supports the visible explanation, but it does not change backend scoring.

Data confidence may consider:

- active enrichment source metadata;
- count of active enrichment factors;
- active crossing factors;
- active weather provider metadata;
- active real telemetry metadata only if the backend reports it.

It must always carry the caveat that confidence is not a safety guarantee.

## Alternative Comparison

Alternative comparison can say:

- selected route has the highest score among returned alternatives;
- selected route is faster/slower by a computed minute delta;
- selected route balances time and score.

It cannot say a route is objectively safe, unsafe, dangerous, or guaranteed better beyond the returned data.
