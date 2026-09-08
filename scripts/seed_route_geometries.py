import asyncio
import sys
import os
import math
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import AsyncSessionLocal
from app.models.route import Route
from app.models.stop import Stop
from app.models.route_stop import RouteStop
from app.models.vehicle import Vehicle, VehicleType
from app.models.device import Device, DeviceStatus
from app.models.telemetry import TelemetryLatest
from app.models.vehicle_route import VehicleRoute
from app.models.department import Department
from sqlalchemy import select

def interpolate_points(p1, p2, num_steps=10):
    """Linearly interpolate between two (lat, lng) points."""
    points = []
    lat1, lng1 = p1
    lat2, lng2 = p2
    for i in range(num_steps + 1):
        frac = i / float(num_steps)
        lat = round(lat1 + (lat2 - lat1) * frac, 6)
        lng = round(lng1 + (lng2 - lng1) * frac, 6)
        points.append((lat, lng))
    return points

def build_dense_route(key_stops, steps_per_segment=15):
    """Build a continuous sequence of waypoints between stops."""
    dense_path = []
    for i in range(len(key_stops) - 1):
        seg = interpolate_points(key_stops[i], key_stops[i + 1], steps_per_segment)
        if i > 0:
            seg = seg[1:]  # avoid duplicate point
        dense_path.extend(seg)
    return dense_path

# Detailed Bikaner transit paths (stop coordinates + intermediate roadway waypoints)
BIKANER_ROUTE_PATHS = {
    "BKN-L1": [
        (28.0812, 73.3754),  # Beechwal RIICO Hub
        (28.0770, 73.3685),
        (28.0720, 73.3610),  # Engineering College Gate
        (28.0600, 73.3480),
        (28.0500, 73.3380),
        (28.0415, 73.3295),  # Lalgarh Palace & Station
        (28.0320, 73.3235),
        (28.0229, 73.3180),  # Junagarh Fort Main Gate
        (28.0195, 73.3155),
        (28.0160, 73.3130),  # KEM Road & Kotgate
        (28.0145, 73.3190),
        (28.0125, 73.3250),  # PBM Hospital Main Gate
        (28.0105, 73.3220),
        (28.0090, 73.3190),  # Rani Bazar Overbridge
        (27.9980, 73.3100),
        (27.9860, 73.3010),  # Ganga Shahar Bus Stand
    ],
    "BKN-L2": [
        (28.0190, 73.3150),  # Bikaner Junction Railway Station
        (28.0225, 73.3185),
        (28.0260, 73.3220),  # Ambedkar Circle
        (28.0245, 73.3200),
        (28.0229, 73.3180),  # Junagarh Fort Main Gate
        (28.0190, 73.3250),
        (28.0150, 73.3320),  # Tulsi Circle
        (28.0115, 73.3350),
        (28.0080, 73.3380),  # Kanta Khaturia Colony
        (28.0050, 73.3415),
        (28.0020, 73.3450),  # JNV Colony Sector 3
        (28.0150, 73.3500),
        (28.0280, 73.3550),  # Karni Nagar Stadium
    ],
    "BKN-L3": [
        (28.0125, 73.3250),  # PBM Hospital Main Gate
        (28.0105, 73.3220),
        (28.0090, 73.3190),  # Rani Bazar Overbridge
        (27.9980, 73.3100),
        (27.9860, 73.3010),  # Ganga Shahar Bus Stand
        (27.9805, 73.2980),
        (27.9750, 73.2950),  # Bhinasar Circle
        (27.9300, 73.3050),
        (27.8800, 73.3200),
        (27.8300, 73.3350),
        (27.7950, 73.3450),  # Deshnoke Karni Mata Stand
    ],
    "BKN-L4": [
        (28.0415, 73.3295),  # Lalgarh Palace & Station
        (28.0340, 73.3260),
        (28.0260, 73.3220),  # Ambedkar Circle
        (28.0245, 73.3200),
        (28.0229, 73.3180),  # Junagarh Fort Main Gate
        (28.0180, 73.3215),
        (28.0125, 73.3250),  # PBM Hospital Main Gate
        (28.0138, 73.3285),
        (28.0150, 73.3320),  # Tulsi Circle
        (28.0085, 73.3385),
        (28.0020, 73.3450),  # JNV Colony Sector 3
    ]
}

async def seed_geometries_and_buses():
    print("[*] Seeding high-resolution GeoJSON geometries for Bikaner transit routes...")
    async with AsyncSessionLocal() as db:
        for code, raw_waypoints in BIKANER_ROUTE_PATHS.items():
            r_res = await db.execute(select(Route).where(Route.code == code))
            route = r_res.scalar_one_or_none()
            if not route:
                print(f"[!] Route {code} not found, skipping.")
                continue

            dense_pts = build_dense_route(raw_waypoints, steps_per_segment=10)
            # GeoJSON coordinates format: [lng, lat]
            geojson_coords = [[lng, lat] for lat, lng in dense_pts]
            route.geometry = {
                "type": "LineString",
                "coordinates": geojson_coords
            }
            print(f"[+] Updated route {code} geometry with {len(geojson_coords)} waypoints.")

        # Ensure Department
        dept_res = await db.execute(select(Department).where(Department.code == "TRANSIT_BKN"))
        dept = dept_res.scalar_one_or_none()
        if not dept:
            dept = Department(
                name="Bikaner Municipal E-Transit",
                code="TRANSIT_BKN",
                description="Public electric bus and transit services for Bikaner city",
                is_active=True
            )
            db.add(dept)
            await db.flush()

        # Seed/verify 5 Bikaner Electric Buses
        buses_to_seed = [
            {"code": "BUS-101", "route": "BKN-L1", "make": "Olectra", "model": "K9 E-Bus", "lat": 28.0229, "lng": 73.3180, "dir": "Inbound"},
            {"code": "BUS-102", "route": "BKN-L1", "make": "Tata Motors", "model": "Ultra EV 9m", "lat": 28.0720, "lng": 73.3610, "dir": "Outbound"},
            {"code": "BUS-201", "route": "BKN-L2", "make": "JBM", "model": "Ecolife 12m", "lat": 28.0150, "lng": 73.3320, "dir": "Inbound"},
            {"code": "BUS-301", "route": "BKN-L3", "make": "Switch Mobility", "model": "EiV 12", "lat": 27.9750, "lng": 73.2950, "dir": "Outbound"},
            {"code": "BUS-401", "route": "BKN-L4", "make": "Olectra", "model": "CX2 E-Coach", "lat": 28.0260, "lng": 73.3220, "dir": "Inbound"},
        ]

        now = datetime.now(timezone.utc)
        for b in buses_to_seed:
            # Check Vehicle
            v_res = await db.execute(select(Vehicle).where(Vehicle.vehicle_code == b["code"]))
            v = v_res.scalar_one_or_none()
            if not v:
                v = Vehicle(
                    vehicle_code=b["code"],
                    registration_number=f"RJ-07-EV-{b['code'].split('-')[1]}",
                    vehicle_type=VehicleType.ELECTRIC_BUS,
                    make=b["make"],
                    model=b["model"],
                    year=2024,
                    department_id=dept.id,
                    is_active=True,
                    public_visible=True
                )
                db.add(v)
                await db.flush()

            # Check Device DEV-BUS-xxx
            dev_code = f"DEV-{b['code']}"
            d_res = await db.execute(select(Device).where(Device.vehicle_id == v.id))
            dev = d_res.scalar_one_or_none()
            if not dev:
                dev = Device(
                    device_code=dev_code,
                    vehicle_id=v.id,
                    firmware_version="v2.4.1",
                    status=DeviceStatus.ACTIVE,
                    last_seen_at=now
                )
                db.add(dev)
                await db.flush()
            else:
                dev.device_code = dev_code
                dev.last_seen_at = now

            # Check Route Link
            r_res = await db.execute(select(Route).where(Route.code == b["route"]))
            route_obj = r_res.scalar_one_or_none()
            if route_obj:
                vr_res = await db.execute(select(VehicleRoute).where(VehicleRoute.vehicle_id == v.id))
                vr = vr_res.scalar_one_or_none()
                if not vr:
                    vr = VehicleRoute(
                        vehicle_id=v.id,
                        route_id=route_obj.id,
                        is_active=True,
                        direction=b["dir"]
                    )
                    db.add(vr)
                else:
                    vr.route_id = route_obj.id
                    vr.is_active = True
                    vr.direction = b["dir"]

            # Telemetry Latest
            t_res = await db.execute(select(TelemetryLatest).where(TelemetryLatest.vehicle_id == v.id))
            tl = t_res.scalar_one_or_none()
            if not tl:
                tl = TelemetryLatest(
                    vehicle_id=v.id,
                    device_id=dev.id,
                    observed_at=now,
                    received_at=now,
                    latitude=b["lat"],
                    longitude=b["lng"],
                    speed_kph=32.0,
                    heading_deg=180.0,
                    soc_pct=85.0,
                    estimated_range_km=212.5,
                    charging=False,
                    connectivity_status="online"
                )
                db.add(tl)
            else:
                tl.device_id = dev.id
                tl.observed_at = now
                tl.received_at = now
                tl.latitude = b["lat"]
                tl.longitude = b["lng"]
                tl.speed_kph = 32.0
                tl.heading_deg = 180.0
                tl.soc_pct = 85.0
                tl.connectivity_status = "online"

        await db.commit()
        print("[SUCCESS] All Bikaner route geometries, buses, devices, and telemetry initialized.")

if __name__ == "__main__":
    asyncio.run(seed_geometries_and_buses())
