"""Generate reproducible, road-snapped Bikaner bus shapes with OSRM.

This is a build/seed utility, not a runtime dependency. It stores the returned
GeoJSON locally so production rendering and simulation do not depend on a
third-party routing service being available.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


OSRM_BASE_URL = "https://router.project-osrm.org/route/v1/driving"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "bikaner_road_shapes.json"

# Only real passenger stops are sent as via-points. OSRM snaps each coordinate
# to its routable street graph and returns every road bend between stops.
ROUTE_STOPS: dict[str, list[tuple[float, float]]] = {
    "BKN-L1": [
        (28.0812, 73.3754), (28.0720, 73.3610), (28.0415, 73.3295),
        (28.0229, 73.3180), (28.0160, 73.3130), (28.0125, 73.3250),
        (28.0090, 73.3190), (27.9860, 73.3010),
    ],
    "BKN-L2": [
        (28.0190, 73.3150), (28.0260, 73.3220), (28.0229, 73.3180),
        (28.0150, 73.3320), (28.0080, 73.3380), (28.0020, 73.3450),
        (28.0280, 73.3550),
    ],
    "BKN-L3": [
        (28.0125, 73.3250), (28.0090, 73.3190), (27.9860, 73.3010),
        (27.9750, 73.2950), (27.7950, 73.3450),
    ],
    "BKN-L4": [
        (28.0415, 73.3295), (28.0260, 73.3220), (28.0229, 73.3180),
        (28.0125, 73.3250), (28.0150, 73.3320), (28.0020, 73.3450),
    ],
}


def fetch_shape(code: str, stops: list[tuple[float, float]]) -> dict:
    coordinates = ";".join(f"{lng:.6f},{lat:.6f}" for lat, lng in stops)
    query = urlencode({"overview": "full", "geometries": "geojson", "steps": "false"})
    request = Request(
        f"{OSRM_BASE_URL}/{coordinates}?{query}",
        headers={"User-Agent": "ChargeEase-route-seed/1.0"},
    )
    with urlopen(request, timeout=45) as response:
        payload = json.load(response)

    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise RuntimeError(f"OSRM failed for {code}: {payload.get('message', payload.get('code'))}")

    route = payload["routes"][0]
    snapped_waypoints = [waypoint["location"] for waypoint in payload.get("waypoints", [])]
    return {
        "type": "LineString",
        "coordinates": route["geometry"]["coordinates"],
        "distance_m": round(route["distance"]),
        "typical_duration_s": round(route["duration"]),
        "snapped_stops": snapped_waypoints,
        "source": "OSRM/OpenStreetMap road graph",
    }


def main() -> None:
    shapes = {code: fetch_shape(code, stops) for code, stops in ROUTE_STOPS.items()}
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(shapes, indent=2), encoding="utf-8")
    for code, shape in shapes.items():
        print(
            f"{code}: {len(shape['coordinates'])} road points, "
            f"{shape['distance_m'] / 1000:.1f} km"
        )
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
