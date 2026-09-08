"""Source-aware timetable helpers for the Bikaner planning simulation.

The public route chart does not include an operator timetable.  Consequently,
the timings in ``bikaner_transit_plan.json`` are deliberately classified as a
planning scenario and are never exposed as authoritative passenger information.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


PLAN_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "bikaner_transit_plan.json"
ROUTE_INDEX_TO_CODE = {14: "BKN-L1", 15: "BKN-L2", 16: "BKN-L3", 17: "BKN-L4"}


def _minutes(value: str) -> int:
    hour, minute = (int(part) for part in value.split(":"))
    return hour * 60 + minute


@lru_cache(maxsize=1)
def get_transit_plan() -> dict:
    with PLAN_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_route_schedule(route_index: int, vehicle_code: str) -> dict | None:
    route_code = ROUTE_INDEX_TO_CODE.get(route_index)
    if not route_code:
        return None
    raw = get_transit_plan()["simulation_routes"].get(route_code)
    if not raw:
        return None
    schedule = dict(raw)
    schedule["route_code"] = route_code
    schedule["service_start_minute"] = _minutes(raw["service_start"])
    schedule["service_end_minute"] = _minutes(raw["service_end"])
    schedule["departure_offset_minutes"] = int(raw["vehicles"].get(vehicle_code.upper(), 0))
    return schedule


def get_public_plan() -> dict:
    """Return a JSON-safe catalog plus the current scenario schedule."""
    return get_transit_plan()

