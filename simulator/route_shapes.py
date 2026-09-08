"""Shared access to locally cached, road-snapped transit shapes."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


SHAPES_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "bikaner_road_shapes.json"


@lru_cache(maxsize=1)
def load_bikaner_shapes() -> dict[str, dict]:
    if not SHAPES_PATH.exists():
        return {}
    return json.loads(SHAPES_PATH.read_text(encoding="utf-8"))


def get_bikaner_geojson(route_code: str) -> dict | None:
    shape = load_bikaner_shapes().get(route_code)
    if not shape:
        return None
    return {"type": "LineString", "coordinates": shape["coordinates"]}


def get_bikaner_simulator_points(route_code: str) -> list[tuple[float, float]]:
    shape = load_bikaner_shapes().get(route_code)
    if not shape:
        return []
    return [(float(lat), float(lng)) for lng, lat in shape["coordinates"]]
