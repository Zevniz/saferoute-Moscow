# Transit Roadmap

Transit is intentionally not shown in the live SafeRoute v2 mode switch. The current release ships only real road navigation for `walk`, `bike`, and `car`.

## Phase 2 Requirements

- Obtain a reliable Moscow GTFS feed or equivalent transit schedule source.
- Add transit graph ingestion and refresh jobs.
- Add stop search and stop-to-stop routing.
- Combine walk legs and transit legs into one route response.
- Normalize transit instructions into the same `instructions[]` contract.
- Add realtime arrivals only if a reliable realtime feed is available.

## UI Reintroduction Criteria

Transit can return to the mode switch only when:

- `/api/route?profile=transit` returns real route candidates.
- Every transit route has real leg metadata, stop names, departure times, and instructions.
- Failure states explain missing service windows or unavailable feeds.
- Tests cover search, routing, and navigation rendering for transit legs.
