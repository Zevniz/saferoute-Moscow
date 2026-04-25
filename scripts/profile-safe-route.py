#!/usr/bin/env python3
"""Print EXPLAIN ANALYZE plans for canonical SafeRoute safety routes."""

from __future__ import annotations

from app.services.routing import explain_safe_route

ORIGIN = (55.7558, 37.6173)
DESTINATION = (55.7298, 37.6030)

for profile in ("walk", "bike", "car"):
    print(f"\n=== {profile} ===")
    for line in explain_safe_route(profile, ORIGIN[0], ORIGIN[1], DESTINATION[0], DESTINATION[1]):
        print(line)
