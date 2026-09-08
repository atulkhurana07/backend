import asyncio
import sys
import os
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import AsyncSessionLocal, engine
from app.models import Base
from app.models.city import City
from app.models.charging_center import ChargingCenter, ChargingCenterStatus
from app.models.route import Route
from app.models.stop import Stop
from app.models.route_stop import RouteStop
from app.models.vehicle import Vehicle, VehicleType
from app.models.device import Device, DeviceStatus
from app.models.telemetry import TelemetryLatest
from app.models.vehicle_route import VehicleRoute
from app.models.department import Department
from sqlalchemy import select

def interpolate_points(p1, p2, num_steps=8):
    points = []
    lat1, lng1 = p1
    lat2, lng2 = p2
    for i in range(num_steps + 1):
        frac = i / float(num_steps)
        lat = round(lat1 + (lat2 - lat1) * frac, 6)
        lng = round(lng1 + (lng2 - lng1) * frac, 6)
        points.append((lat, lng))
    return points

def build_dense_route(key_stops, steps_per_segment=8):
    dense_path = []
    for i in range(len(key_stops) - 1):
        seg = interpolate_points(key_stops[i], key_stops[i + 1], steps_per_segment)
        if i > 0:
            seg = seg[1:]
        dense_path.extend(seg)
    return dense_path

# 1. Jaipur Stops (Interchanges & Key Passenger Stations)
JAIPUR_STOPS = [
    # Line 1 Stops (Pink Line: Mansarovar to Badi Chaupar)
    {"name": "Mansarovar Metro Terminal", "code": "JPR-MSV", "latitude": 26.8795, "longitude": 75.7562, "city": "Jaipur", "state": "Rajasthan", "address": "Mansarovar Metro Station, Bhrigu Path"},
    {"name": "New Aatish Market", "code": "JPR-ATM", "latitude": 26.8835, "longitude": 75.7645, "city": "Jaipur", "state": "Rajasthan", "address": "Gopalpura Bypass, New Aatish Market"},
    {"name": "Vivek Vihar", "code": "JPR-VKV", "latitude": 26.8885, "longitude": 75.7715, "city": "Jaipur", "state": "Rajasthan", "address": "Vivek Vihar Metro Circle"},
    {"name": "Shyam Nagar", "code": "JPR-SHY", "latitude": 26.8945, "longitude": 75.7760, "city": "Jaipur", "state": "Rajasthan", "address": "Ajmer Road, Shyam Nagar"},
    {"name": "Ram Nagar", "code": "JPR-RMN", "latitude": 26.8995, "longitude": 75.7810, "city": "Jaipur", "state": "Rajasthan", "address": "Hawa Sadak, Ram Nagar"},
    {"name": "Civil Lines", "code": "JPR-CVL", "latitude": 26.9065, "longitude": 75.7870, "city": "Jaipur", "state": "Rajasthan", "address": "Jacob Road, Civil Lines"},
    {"name": "Jaipur Junction Railway Station", "code": "JPR-RLY", "latitude": 26.9195, "longitude": 75.7885, "city": "Jaipur", "state": "Rajasthan", "address": "Station Road Platform 1, Hasanpura"},
    {"name": "Sindhi Camp Central Bus Stand", "code": "JPR-SCB", "latitude": 26.9235, "longitude": 75.7985, "city": "Jaipur", "state": "Rajasthan", "address": "ISBT Sindhi Camp, Station Road"},
    {"name": "Chandpole Gate & Metro", "code": "JPR-CPG", "latitude": 26.9255, "longitude": 75.8115, "city": "Jaipur", "state": "Rajasthan", "address": "Chandpole Bazar Entry, Old Pink City"},
    {"name": "Chhoti Chaupar", "code": "JPR-CHC", "latitude": 26.9258, "longitude": 75.8200, "city": "Jaipur", "state": "Rajasthan", "address": "Chhoti Chaupar Heritage Circle"},
    {"name": "Badi Chaupar (Hawa Mahal)", "code": "JPR-BDC", "latitude": 26.9240, "longitude": 75.8270, "city": "Jaipur", "state": "Rajasthan", "address": "Opp. Hawa Mahal, Badi Chaupar"},

    # Line 2 Stops (Amber Express: Sindhi Camp to Amer Fort)
    {"name": "Khasa Kothi Circle", "code": "JPR-KSK", "latitude": 26.9190, "longitude": 75.7940, "city": "Jaipur", "state": "Rajasthan", "address": "MI Road & Khasa Kothi Circle"},
    {"name": "Ajmeri Gate", "code": "JPR-AJG", "latitude": 26.9180, "longitude": 75.8180, "city": "Jaipur", "state": "Rajasthan", "address": "Ajmeri Gate Chauraha, Kishanpole"},
    {"name": "Sanganeri Gate", "code": "JPR-SNG", "latitude": 26.9160, "longitude": 75.8245, "city": "Jaipur", "state": "Rajasthan", "address": "Sanganeri Gate Market Circle"},
    {"name": "Jorawar Singh Gate", "code": "JPR-JSG", "latitude": 26.9380, "longitude": 75.8360, "city": "Jaipur", "state": "Rajasthan", "address": "Amer Road North Gate"},
    {"name": "Jal Mahal Promenade", "code": "JPR-JMH", "latitude": 26.9535, "longitude": 75.8465, "city": "Jaipur", "state": "Rajasthan", "address": "Man Sagar Lake Viewpoint, Amer Road"},
    {"name": "Amer Fort & Palace Stand", "code": "JPR-AMR", "latitude": 26.9855, "longitude": 75.8510, "city": "Jaipur", "state": "Rajasthan", "address": "Amer Palace Entrance, Devisinghpura"},

    # Line 3 Stops (Airport Express: Airport T2 to Vaishali Nagar)
    {"name": "Jaipur International Airport (Terminal 2)", "code": "JPR-AIR", "latitude": 26.8285, "longitude": 75.8055, "city": "Jaipur", "state": "Rajasthan", "address": "Arrivals Gate 1, Airport Terminal 2"},
    {"name": "Jawahar Circle Garden", "code": "JPR-JWC", "latitude": 26.8435, "longitude": 75.8020, "city": "Jaipur", "state": "Rajasthan", "address": "JLND Marg, Jawahar Circle"},
    {"name": "Durgapura Railway Station", "code": "JPR-DGP", "latitude": 26.8570, "longitude": 75.7950, "city": "Jaipur", "state": "Rajasthan", "address": "Tonk Road, Durgapura"},
    {"name": "Gopalpura Bypass Circle", "code": "JPR-GPL", "latitude": 26.8720, "longitude": 75.7860, "city": "Jaipur", "state": "Rajasthan", "address": "Gopalpura Flyover Circle"},
    {"name": "Sodala Elevated Junction", "code": "JPR-SDL", "latitude": 26.9020, "longitude": 75.7760, "city": "Jaipur", "state": "Rajasthan", "address": "Ajmer Road, Sodala Chauraha"},
    {"name": "Queens Road Corner", "code": "JPR-QRD", "latitude": 26.9080, "longitude": 75.7530, "city": "Jaipur", "state": "Rajasthan", "address": "Queens Road & Vaishali Entry"},
    {"name": "Amrapali Circle (Vaishali Nagar)", "code": "JPR-AMP", "latitude": 26.9135, "longitude": 75.7420, "city": "Jaipur", "state": "Rajasthan", "address": "Amrapali Plaza, Vaishali Nagar"},

    # Line 4 Stops (Southern Knowledge & Tech Corridor: Jagatpura to Vidhyadhar Nagar)
    {"name": "Jagatpura Railway Station", "code": "JPR-JGT", "latitude": 26.8340, "longitude": 75.8450, "city": "Jaipur", "state": "Rajasthan", "address": "Jagatpura Flyover Junction"},
    {"name": "Malviya Nagar (WTP & MNIT)", "code": "JPR-MLV", "latitude": 26.8530, "longitude": 75.8130, "city": "Jaipur", "state": "Rajasthan", "address": "JLND Marg, Opp. World Trade Park"},
    {"name": "Apex Circle", "code": "JPR-APX", "latitude": 26.8620, "longitude": 75.8080, "city": "Jaipur", "state": "Rajasthan", "address": "Malviya Nagar Institutional Area"},
    {"name": "Gandhi Nagar Railway Station", "code": "JPR-GND", "latitude": 26.8780, "longitude": 75.8010, "city": "Jaipur", "state": "Rajasthan", "address": "Tonk Road, Gandhi Nagar"},
    {"name": "Rambagh Circle", "code": "JPR-RMB", "latitude": 26.8970, "longitude": 75.8060, "city": "Jaipur", "state": "Rajasthan", "address": "SMS Stadium, Rambagh Circle"},
    {"name": "SMS Hospital Gate", "code": "JPR-SMS", "latitude": 26.9080, "longitude": 75.8140, "city": "Jaipur", "state": "Rajasthan", "address": "JLN Marg, SMS Medical College"},
    {"name": "Panch Batti / MI Road", "code": "JPR-PBT", "latitude": 26.9170, "longitude": 75.8160, "city": "Jaipur", "state": "Rajasthan", "address": "MI Road Commercial Zone"},
    {"name": "Government Secretariat", "code": "JPR-SEC", "latitude": 26.9090, "longitude": 75.7950, "city": "Jaipur", "state": "Rajasthan", "address": "Bhagwan Das Road, Secretariat"},
    {"name": "Collectorate Circle", "code": "JPR-COL", "latitude": 26.9290, "longitude": 75.7910, "city": "Jaipur", "state": "Rajasthan", "address": "Bani Park, Collectorate"},
    {"name": "Vidhyadhar Nagar Stadium", "code": "JPR-VDN", "latitude": 26.9650, "longitude": 75.7820, "city": "Jaipur", "state": "Rajasthan", "address": "Sector 3 Stadium, Vidhyadhar Nagar"},

    # Line 5 Stops (Industrial Clean Shuttle: Sitapura to Sanganer)
    {"name": "Sitapura Industrial RIICO Gate", "code": "JPR-STP", "latitude": 26.7720, "longitude": 75.8380, "city": "Jaipur", "state": "Rajasthan", "address": "Tonk Road, Sitapura Industrial Zone"},
    {"name": "Mahatma Gandhi Hospital", "code": "JPR-MGH", "latitude": 26.7820, "longitude": 75.8420, "city": "Jaipur", "state": "Rajasthan", "address": "RIICO Institutional Area, Sitapura"},
    {"name": "Pratap Nagar Sector 11", "code": "JPR-PRT", "latitude": 26.8020, "longitude": 75.8260, "city": "Jaipur", "state": "Rajasthan", "address": "Haldighati Marg, Pratap Nagar"},
    {"name": "Sanganer Bus Terminus", "code": "JPR-SNG-TM", "latitude": 26.8180, "longitude": 75.7710, "city": "Jaipur", "state": "Rajasthan", "address": "Old Sanganer Town Bus Stand"},
]

# 2. Jaipur Transit Corridors (Lines 1 to 5)
JAIPUR_ROUTES = [
    {
        "name": "Line 1 (Pink Heritage Metro Corridor): Mansarovar ⇄ Badi Chaupar",
        "code": "JPR-L1",
        "city": "Jaipur",
        "state": "Rajasthan",
        "description": "High-frequency East-West rapid electric transit connecting residential Mansarovar to the historic Walled City & Hawa Mahal.",
        "color": "#ec4899",
        "stops": [
            "Mansarovar Metro Terminal", "New Aatish Market", "Vivek Vihar", "Shyam Nagar",
            "Ram Nagar", "Civil Lines", "Jaipur Junction Railway Station", "Sindhi Camp Central Bus Stand",
            "Chandpole Gate & Metro", "Chhoti Chaupar", "Badi Chaupar (Hawa Mahal)"
        ],
        "waypoints": [
            (26.8795, 75.7562), (26.8835, 75.7645), (26.8885, 75.7715), (26.8945, 75.7760),
            (26.8995, 75.7810), (26.9065, 75.7870), (26.9195, 75.7885), (26.9235, 75.7985),
            (26.9255, 75.8115), (26.9258, 75.8200), (26.9240, 75.8270)
        ]
    },
    {
        "name": "Line 2 (Green Amber Express): Sindhi Camp ⇄ Amer Fort",
        "code": "JPR-L2",
        "city": "Jaipur",
        "state": "Rajasthan",
        "description": "Scenic tourism & commuter express linking Jaipur's central bus interchange directly with the UNESCO World Heritage Amer Fort.",
        "color": "#10b981",
        "stops": [
            "Sindhi Camp Central Bus Stand", "Khasa Kothi Circle", "Ajmeri Gate", "Sanganeri Gate",
            "Badi Chaupar (Hawa Mahal)", "Jorawar Singh Gate", "Jal Mahal Promenade", "Amer Fort & Palace Stand"
        ],
        "waypoints": [
            (26.9235, 75.7985), (26.9190, 75.7940), (26.9180, 75.8180), (26.9160, 75.8245),
            (26.9240, 75.8270), (26.9380, 75.8360), (26.9535, 75.8465), (26.9855, 75.8510)
        ]
    },
    {
        "name": "Line 3 (Blue Airport Express): Airport Terminal 2 ⇄ Vaishali Nagar",
        "code": "JPR-L3",
        "city": "Jaipur",
        "state": "Rajasthan",
        "description": "Fast arterial airport corridor traversing JLN Marg, Durgapura, Sodala Elevated Road, and West Jaipur commercial districts.",
        "color": "#0284c7",
        "stops": [
            "Jaipur International Airport (Terminal 2)", "Jawahar Circle Garden", "Durgapura Railway Station",
            "Gopalpura Bypass Circle", "Sodala Elevated Junction", "Queens Road Corner", "Amrapali Circle (Vaishali Nagar)"
        ],
        "waypoints": [
            (26.8285, 75.8055), (26.8435, 75.8020), (26.8570, 75.7950), (26.8720, 75.7860),
            (26.9020, 75.7760), (26.9080, 75.7530), (26.9135, 75.7420)
        ]
    },
    {
        "name": "Line 4 (Orange Knowledge & Tech Line): Jagatpura ⇄ Vidhyadhar Nagar",
        "code": "JPR-L4",
        "city": "Jaipur",
        "state": "Rajasthan",
        "description": "Cross-city transit spine serving educational hubs (MNIT), shopping districts (WTP), healthcare (SMS Hospital), and north suburbs.",
        "color": "#f97316",
        "stops": [
            "Jagatpura Railway Station", "Malviya Nagar (WTP & MNIT)", "Apex Circle",
            "Gandhi Nagar Railway Station", "Rambagh Circle", "SMS Hospital Gate",
            "Panch Batti / MI Road", "Government Secretariat", "Collectorate Circle", "Vidhyadhar Nagar Stadium"
        ],
        "waypoints": [
            (26.8340, 75.8450), (26.8530, 75.8130), (26.8620, 75.8080), (26.8780, 75.8010),
            (26.8970, 75.8060), (26.9080, 75.8140), (26.9170, 75.8160), (26.9090, 75.7950),
            (26.9290, 75.7910), (26.9650, 75.7820)
        ]
    },
    {
        "name": "Line 5 (Purple Clean Industrial Shuttle): Sitapura RIICO ⇄ Sanganer Terminus",
        "code": "JPR-L5",
        "city": "Jaipur",
        "state": "Rajasthan",
        "description": "Dedicated workforce and student zero-emission shuttle connecting Sitapura Industrial Zone, hospitals, and Sanganer town.",
        "color": "#8b5cf6",
        "stops": [
            "Sitapura Industrial RIICO Gate", "Mahatma Gandhi Hospital", "Pratap Nagar Sector 11",
            "Sanganer Bus Terminus"
        ],
        "waypoints": [
            (26.7720, 75.8380), (26.7820, 75.8420), (26.8020, 75.8260), (26.8180, 75.7710)
        ]
    }
]

# 3. Jaipur EV Charging Hubs along transit corridors
JAIPUR_CHARGING_CENTERS = [
    {
        "name": "Tata Power EZ Charge - Sindhi Camp ISBT Hub",
        "latitude": 26.9238,
        "longitude": 75.7988,
        "address": "Opp. Bus Stand Terminal 2, Sindhi Camp, Jaipur",
        "city": "Jaipur",
        "state": "Rajasthan",
        "pincode": "302001",
        "status": ChargingCenterStatus.OPERATIONAL,
        "power_kw": 120.0,
        "contact_phone": "+91 1800 209 5161",
        "operating_hours": "24/7 Open",
        "description": "High-capacity ultra-fast DC charging hub for public transit buses, commercial cabs, and passenger EVs.",
        "connectors": {"CCS2": 4, "Type2": 2, "GB/T": 2, "fast_dc": True},
        "amenities": {"restroom": True, "waiting_lounge": True, "wifi": True, "pricing_inr_kwh": 18.0},
        "public_visible": True,
    },
    {
        "name": "Jadhao EV Fast Charging - Airport Plaza T2",
        "latitude": 26.8290,
        "longitude": 75.8060,
        "address": "Terminal 2 Commercial Car Parking, Sanganer, Jaipur",
        "city": "Jaipur",
        "state": "Rajasthan",
        "pincode": "302029",
        "status": ChargingCenterStatus.OPERATIONAL,
        "power_kw": 150.0,
        "contact_phone": "+91 141 279 2828",
        "operating_hours": "24/7 Open",
        "description": "Supercharger facility at Jaipur Airport with dual-gun 150kW CCS2 dispensers.",
        "connectors": {"CCS2": 4, "fast_dc": True},
        "amenities": {"restroom": True, "cafe": True, "security_24x7": True, "pricing_inr_kwh": 19.5},
        "public_visible": True,
    },
    {
        "name": "ChargeZone Hub - Jaipur Junction Station",
        "latitude": 26.9198,
        "longitude": 75.7890,
        "address": "Station Parking Lot, Hasanpura Road, Jaipur",
        "city": "Jaipur",
        "state": "Rajasthan",
        "pincode": "302006",
        "status": ChargingCenterStatus.OPERATIONAL,
        "power_kw": 60.0,
        "contact_phone": "+91 8000 333 444",
        "operating_hours": "24/7 Open",
        "description": "Railway station multi-modal transit charging center.",
        "connectors": {"CCS2": 2, "Type2": 2},
        "amenities": {"restroom": True, "food_court": True, "pricing_inr_kwh": 17.5},
        "public_visible": True,
    },
    {
        "name": "Statiq Smart Hub - Mansarovar Metro",
        "latitude": 26.8798,
        "longitude": 75.7565,
        "address": "Mansarovar Metro Parking Complex, Jaipur",
        "city": "Jaipur",
        "state": "Rajasthan",
        "pincode": "302020",
        "status": ChargingCenterStatus.OPERATIONAL,
        "power_kw": 60.0,
        "contact_phone": "+91 9999 123 456",
        "operating_hours": "05:00 AM - 11:30 PM",
        "description": "Commuter park-and-charge EV station at western terminal of Pink Line Metro.",
        "connectors": {"CCS2": 2, "Type2": 2},
        "amenities": {"restroom": True, "pricing_inr_kwh": 16.5},
        "public_visible": True,
    },
    {
        "name": "Volttic DC Station - World Trade Park (Malviya Nagar)",
        "latitude": 26.8535,
        "longitude": 75.8135,
        "address": "WTP South Block Basement EV Zone, JLN Marg, Jaipur",
        "city": "Jaipur",
        "state": "Rajasthan",
        "pincode": "302017",
        "status": ChargingCenterStatus.OPERATIONAL,
        "power_kw": 50.0,
        "contact_phone": "+91 141 400 5000",
        "operating_hours": "10:00 AM - 11:00 PM",
        "description": "Retail destination fast charger for shoppers and JLN corridor commuters.",
        "connectors": {"CCS2": 2, "Type2": 2},
        "amenities": {"restroom": True, "cafe": True, "wifi": True, "pricing_inr_kwh": 18.5},
        "public_visible": True,
    }
]

# 4. Jaipur Electric Bus Fleet
JAIPUR_BUSES = [
    {"code": "JPR-BUS-101", "route": "JPR-L1", "make": "Olectra", "model": "K9 E-Bus", "lat": 26.9065, "lng": 75.7870, "speed": 38.0, "heading": 65.0, "soc": 88.0, "reg": "RJ-14-EV-1001"},
    {"code": "JPR-BUS-102", "route": "JPR-L1", "make": "Tata Motors", "model": "Ultra EV 9m", "lat": 26.9255, "lng": 75.8115, "speed": 29.0, "heading": 90.0, "soc": 72.0, "reg": "RJ-14-EV-1002"},
    {"code": "JPR-BUS-201", "route": "JPR-L2", "make": "JBM", "model": "Ecolife 12m", "lat": 26.9535, "lng": 75.8465, "speed": 44.0, "heading": 15.0, "soc": 94.0, "reg": "RJ-14-EV-2001"},
    {"code": "JPR-BUS-202", "route": "JPR-L2", "make": "Olectra", "model": "K9 E-Bus", "lat": 26.9240, "lng": 75.8270, "speed": 32.0, "heading": 190.0, "soc": 65.0, "reg": "RJ-14-EV-2002"},
    {"code": "JPR-BUS-301", "route": "JPR-L3", "make": "Switch Mobility", "model": "EiV 12", "lat": 26.8570, "lng": 75.7950, "speed": 52.0, "heading": 340.0, "soc": 81.0, "reg": "RJ-14-EV-3001"},
    {"code": "JPR-BUS-302", "route": "JPR-L3", "make": "Tata Motors", "model": "Ultra EV 9m", "lat": 26.9020, "lng": 75.7760, "speed": 36.0, "heading": 280.0, "soc": 58.0, "reg": "RJ-14-EV-3002"},
    {"code": "JPR-BUS-401", "route": "JPR-L4", "make": "JBM", "model": "Ecolife 12m", "lat": 26.8780, "lng": 75.8010, "speed": 40.0, "heading": 355.0, "soc": 77.0, "reg": "RJ-14-EV-4001"},
    {"code": "JPR-BUS-501", "route": "JPR-L5", "make": "Olectra", "model": "CX2 E-Coach", "lat": 26.7820, "lng": 75.8420, "speed": 46.0, "heading": 170.0, "soc": 84.0, "reg": "RJ-14-EV-5001"},
]

async def seed_jaipur():
    print("[*] Starting Jaipur Clean Transit Network Database Seeding...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Ensure City exists
        c_res = await db.execute(select(City).where(City.name.ilike("Jaipur")))
        city_obj = c_res.scalar_one_or_none()
        if not city_obj:
            city_obj = City(name="Jaipur", state="Rajasthan", latitude=26.9124, longitude=75.7873, is_active=True)
            db.add(city_obj)
            await db.flush()
        print(f"[+] Verified Jaipur City (id={city_obj.id}).")

        # 1. Seed Jaipur Stops
        stops_map = {}
        for s_data in JAIPUR_STOPS:
            existing = await db.execute(select(Stop).where(Stop.name == s_data["name"]))
            stop_obj = existing.scalar_one_or_none()
            if not stop_obj:
                stop_obj = Stop(**s_data)
                db.add(stop_obj)
                await db.flush()
            else:
                for k, v in s_data.items():
                    setattr(stop_obj, k, v)
                await db.flush()
            stops_map[s_data["name"]] = stop_obj
        await db.commit()
        print(f"[+] Seeded {len(JAIPUR_STOPS)} Jaipur Passenger Stops/Interchanges.")

        # 2. Seed Jaipur Corridors (Routes) with dense GeoJSON geometries
        routes_map = {}
        for r_data in JAIPUR_ROUTES:
            dense_coords = build_dense_route(r_data["waypoints"], steps_per_segment=8)
            geojson_coords = [[lng, lat] for lat, lng in dense_coords]

            r_query = await db.execute(select(Route).where(Route.code == r_data["code"]))
            route_obj = r_query.scalar_one_or_none()
            if not route_obj:
                route_obj = Route(
                    name=r_data["name"],
                    code=r_data["code"],
                    city=r_data["city"],
                    state=r_data["state"],
                    description=r_data["description"],
                    color=r_data["color"],
                    geometry={"type": "LineString", "coordinates": geojson_coords},
                    is_active=True
                )
                db.add(route_obj)
                await db.flush()
            else:
                route_obj.name = r_data["name"]
                route_obj.city = r_data["city"]
                route_obj.state = r_data["state"]
                route_obj.description = r_data["description"]
                route_obj.color = r_data["color"]
                route_obj.geometry = {"type": "LineString", "coordinates": geojson_coords}
                await db.flush()
            routes_map[r_data["code"]] = route_obj

            # Route Stops association
            for seq, stop_name in enumerate(r_data["stops"]):
                s_obj = stops_map.get(stop_name)
                if s_obj:
                    rs_query = await db.execute(
                        select(RouteStop).where(RouteStop.route_id == route_obj.id, RouteStop.stop_id == s_obj.id)
                    )
                    rs_obj = rs_query.scalar_one_or_none()
                    if not rs_obj:
                        db.add(RouteStop(
                            route_id=route_obj.id,
                            stop_id=s_obj.id,
                            sequence=seq + 1,
                            distance_from_start_km=round((seq + 1) * 1.6, 1)
                        ))
                    else:
                        rs_obj.sequence = seq + 1
                        rs_obj.distance_from_start_km = round((seq + 1) * 1.6, 1)
        await db.commit()
        print(f"[+] Seeded {len(JAIPUR_ROUTES)} Jaipur Transit Corridors with dense geometries.")

        # 3. Seed Jaipur Charging Centers
        for cc_data in JAIPUR_CHARGING_CENTERS:
            existing = await db.execute(select(ChargingCenter).where(ChargingCenter.name == cc_data["name"]))
            cc_obj = existing.scalar_one_or_none()
            if not cc_obj:
                db.add(ChargingCenter(**cc_data, last_verified_at=datetime.now(timezone.utc)))
            else:
                for k, v in cc_data.items():
                    setattr(cc_obj, k, v)
                cc_obj.last_verified_at = datetime.now(timezone.utc)
        await db.commit()
        print(f"[+] Seeded {len(JAIPUR_CHARGING_CENTERS)} Jaipur Transit-Connected EV Charging Hubs.")

        # 4. Seed Jaipur Department & Electric Buses
        dept_res = await db.execute(select(Department).where(Department.code == "TRANSIT_JPR"))
        dept = dept_res.scalar_one_or_none()
        if not dept:
            dept = Department(
                name="Jaipur Smart City Transit",
                code="TRANSIT_JPR",
                description="Public municipal electric transit and feeder network for Jaipur Metropolitan Area",
                is_active=True
            )
            db.add(dept)
            await db.flush()

        now = datetime.now(timezone.utc)
        for b in JAIPUR_BUSES:
            v_res = await db.execute(select(Vehicle).where(Vehicle.vehicle_code == b["code"]))
            v_obj = v_res.scalar_one_or_none()
            if not v_obj:
                v_obj = Vehicle(
                    vehicle_code=b["code"],
                    registration_number=b["reg"],
                    vehicle_type=VehicleType.ELECTRIC_BUS,
                    make=b["make"],
                    model=b["model"],
                    year=2024,
                    department_id=dept.id,
                    is_active=True,
                    public_visible=True
                )
                db.add(v_obj)
                await db.flush()

            # Device
            dev_code = f"DEV-{b['code']}"
            d_res = await db.execute(select(Device).where(Device.vehicle_id == v_obj.id))
            dev = d_res.scalar_one_or_none()
            if not dev:
                dev = Device(
                    device_code=dev_code,
                    vehicle_id=v_obj.id,
                    firmware_version="v3.1.0",
                    status=DeviceStatus.ACTIVE,
                    last_seen_at=now
                )
                db.add(dev)
                await db.flush()

            # Vehicle Route
            r_obj = routes_map.get(b["route"])
            if r_obj:
                vr_res = await db.execute(select(VehicleRoute).where(VehicleRoute.vehicle_id == v_obj.id))
                vr = vr_res.scalar_one_or_none()
                if not vr:
                    db.add(VehicleRoute(vehicle_id=v_obj.id, route_id=r_obj.id, is_active=True, direction="Inbound"))
                else:
                    vr.route_id = r_obj.id
                    vr.is_active = True

            # Telemetry
            t_res = await db.execute(select(TelemetryLatest).where(TelemetryLatest.vehicle_id == v_obj.id))
            tl = t_res.scalar_one_or_none()
            if not tl:
                tl = TelemetryLatest(
                    vehicle_id=v_obj.id,
                    device_id=dev.id,
                    observed_at=now,
                    received_at=now,
                    latitude=b["lat"],
                    longitude=b["lng"],
                    speed_kph=b["speed"],
                    heading_deg=b["heading"],
                    soc_pct=b["soc"],
                    estimated_range_km=round(b["soc"] * 2.5, 1),
                    charging=False,
                    connectivity_status="online"
                )
                db.add(tl)
            else:
                tl.observed_at = now
                tl.received_at = now
                tl.latitude = b["lat"]
                tl.longitude = b["lng"]
                tl.speed_kph = b["speed"]
                tl.heading_deg = b["heading"]
                tl.soc_pct = b["soc"]
                tl.connectivity_status = "online"

        await db.commit()
        print(f"[SUCCESS] Seeded {len(JAIPUR_BUSES)} Jaipur Electric Buses and live telemetry.")

if __name__ == "__main__":
    asyncio.run(seed_jaipur())
