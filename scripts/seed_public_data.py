import asyncio
import uuid
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import AsyncSessionLocal, engine
from app.models import Base
from app.models.city import City
from app.models.charging_center import ChargingCenter, ChargingCenterStatus
from app.models.route import Route
from app.models.stop import Stop
from app.models.route_stop import RouteStop
from app.models.help_contact import HelpContact
from app.models.vehicle import Vehicle, VehicleType
from app.models.vehicle_route import VehicleRoute
from sqlalchemy import select

async def seed():
    print("[*] Ensuring database tables exist in Neon PostgreSQL...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[+] Database schema verified.")

    async with AsyncSessionLocal() as db:
        print("[*] Seeding Bikaner & Rajasthan EV Intelligence Data...")

        # 1. Seed Cities
        cities_data = [
            {"name": "Bikaner", "state": "Rajasthan", "latitude": 28.0229, "longitude": 73.3119},
            {"name": "Jaipur", "state": "Rajasthan", "latitude": 26.9124, "longitude": 75.7873},
            {"name": "Jodhpur", "state": "Rajasthan", "latitude": 26.2389, "longitude": 73.0243},
            {"name": "Udaipur", "state": "Rajasthan", "latitude": 24.5854, "longitude": 73.7125},
            {"name": "Delhi", "state": "Delhi", "latitude": 28.7041, "longitude": 77.1025},
        ]
        
        for c_data in cities_data:
            existing = await db.execute(select(City).where(City.name == c_data["name"], City.state == c_data["state"]))
            if not existing.scalar_one_or_none():
                db.add(City(**c_data))
        await db.commit()
        print("[+] Seeded cities.")

        # 2. Seed Real Bikaner EV Charging Centers with Images, Connectors, & Amenities
        bikaner_stations = [
            {
                "name": "Tata Power EZ Charge - Narendra Bhawan Hub",
                "latitude": 28.0185,
                "longitude": 73.3082,
                "address": "Samvite Shikshak Colony, Gandhi Nagar, Bikaner",
                "city": "Bikaner",
                "state": "Rajasthan",
                "pincode": "334001",
                "status": ChargingCenterStatus.OPERATIONAL,
                "power_kw": 60.0,
                "contact_phone": "+91 1800 209 5161",
                "operating_hours": "24/7 Open",
                "description": "High-speed DC Fast Charging hub located at luxury heritage hub with high security, clean cafe, and parking.",
                "connectors": {"CCS2": 2, "Type2": 2, "fast_dc": True},
                "amenities": {
                    "restroom": True, "cafe": True, "wifi": True, "security_24x7": True,
                    "pricing_inr_kwh": 18.5,
                    "image_url": "https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=800&q=80"
                },
                "public_visible": True,
                "last_verified_at": datetime.now(timezone.utc)
            },
            {
                "name": "Jio-bp pulse EV Station - NH-11 Jaipur Highway",
                "latitude": 28.0012,
                "longitude": 73.3685,
                "address": "NH-11 Bikaner-Jaipur Highway, Near Raisar Bypass, Bikaner",
                "city": "Bikaner",
                "state": "Rajasthan",
                "pincode": "334004",
                "status": ChargingCenterStatus.OPERATIONAL,
                "power_kw": 120.0,
                "contact_phone": "+91 1800 891 9023",
                "operating_hours": "24/7 Open",
                "description": "Ultra-fast Highway Dual Gun EV Charging plaza with Wild Bean Cafe, clean washrooms, and EV tyre care.",
                "connectors": {"CCS2": 4, "Type2": 2, "fast_dc": True},
                "amenities": {
                    "restroom": True, "cafe": True, "wifi": True, "food_court": True,
                    "pricing_inr_kwh": 19.0,
                    "image_url": "https://images.unsplash.com/photo-1558441719-20f5b9d365dc?auto=format&fit=crop&w=800&q=80"
                },
                "public_visible": True,
                "last_verified_at": datetime.now(timezone.utc)
            },
            {
                "name": "Statiq EV Charging Hub - Karni Industrial Area",
                "latitude": 28.0581,
                "longitude": 73.3421,
                "address": "Phase 2, Near RIICO Office, Karni Industrial Area, Bikaner",
                "city": "Bikaner",
                "state": "Rajasthan",
                "pincode": "334003",
                "status": ChargingCenterStatus.OPERATIONAL,
                "power_kw": 60.0,
                "contact_phone": "+91 8000 700 800",
                "operating_hours": "06:00 AM - 11:00 PM",
                "description": "Industrial zone fast charging station with multi-vehicle simultaneous charging for commercial & private EVs.",
                "connectors": {"CCS2": 2, "GB/T": 1, "Type2": 2, "fast_dc": True},
                "amenities": {
                    "restroom": True, "parking": True, "pricing_inr_kwh": 17.5,
                    "image_url": "https://images.unsplash.com/photo-1617788138017-80ad40651399?auto=format&fit=crop&w=800&q=80"
                },
                "public_visible": True,
                "last_verified_at": datetime.now(timezone.utc)
            },
            {
                "name": "Kazam EV Charging Point - Lalgarh Palace Complex",
                "latitude": 28.0412,
                "longitude": 73.3288,
                "address": "Samta Nagar, Near Lalgarh Railway Station, Bikaner",
                "city": "Bikaner",
                "state": "Rajasthan",
                "pincode": "334002",
                "status": ChargingCenterStatus.OPERATIONAL,
                "power_kw": 30.0,
                "contact_phone": "+91 9900 112 233",
                "operating_hours": "24/7 Open",
                "description": "Reliable AC/DC charging station near Lalgarh tourist and railway hub.",
                "connectors": {"CCS2": 1, "Type2": 2, "fast_dc": True},
                "amenities": {
                    "restroom": True, "hotel_access": True, "pricing_inr_kwh": 16.0,
                    "image_url": "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=800&q=80"
                },
                "public_visible": True,
                "last_verified_at": datetime.now(timezone.utc)
            },
            {
                "name": "Bikaner SuperFast EV Station - Rani Bazar",
                "latitude": 28.0094,
                "longitude": 73.3195,
                "address": "Road No. 5, Near Railway Overbridge, Rani Bazar, Bikaner",
                "city": "Bikaner",
                "state": "Rajasthan",
                "pincode": "334001",
                "status": ChargingCenterStatus.OPERATIONAL,
                "power_kw": 50.0,
                "contact_phone": "+91 151 223344",
                "operating_hours": "24/7 Open",
                "description": "Central city fast charger equipped with auto-cut off and app-based real-time slot booking.",
                "connectors": {"CCS2": 2, "Type2": 2, "fast_dc": True},
                "amenities": {
                    "restroom": True, "shopping_nearby": True, "pricing_inr_kwh": 18.0,
                    "image_url": "https://images.unsplash.com/photo-1593941707874-ef25b8b4a92b?auto=format&fit=crop&w=800&q=80"
                },
                "public_visible": True,
                "last_verified_at": datetime.now(timezone.utc)
            },
            {
                "name": "GreenCharge Hub - PBM Hospital Medical Zone",
                "latitude": 28.0128,
                "longitude": 73.3256,
                "address": "Sadul Colony, Opp. PBM Hospital Emergency Gate, Bikaner",
                "city": "Bikaner",
                "state": "Rajasthan",
                "pincode": "334003",
                "status": ChargingCenterStatus.OPERATIONAL,
                "power_kw": 30.0,
                "contact_phone": "+91 9414 001122",
                "operating_hours": "24/7 Open",
                "description": "Dedicated EV charging facility for emergency, medical staff, and public visitors in medical zone.",
                "connectors": {"CCS2": 1, "Type2": 2, "Bharat_DC": 1},
                "amenities": {
                    "restroom": True, "pharmacy_24x7": True, "pricing_inr_kwh": 15.5,
                    "image_url": "https://images.unsplash.com/photo-1563986768494-4dee2763ff3f?auto=format&fit=crop&w=800&q=80"
                },
                "public_visible": True,
                "last_verified_at": datetime.now(timezone.utc)
            },
            {
                "name": "EcoCharge Center - Ganga Shahar Main Road",
                "latitude": 27.9865,
                "longitude": 73.3012,
                "address": "Near Acharya Tulsi Samadhi Sthal, Ganga Shahar, Bikaner",
                "city": "Bikaner",
                "state": "Rajasthan",
                "pincode": "334401",
                "status": ChargingCenterStatus.OPERATIONAL,
                "power_kw": 30.0,
                "contact_phone": "+91 9829 556677",
                "operating_hours": "07:00 AM - 11:30 PM",
                "description": "South Bikaner charging center supporting 2W, 3W, and 4W electric vehicles with smart monitoring.",
                "connectors": {"CCS2": 1, "Type2": 2, "15A_Socket": 4},
                "amenities": {
                    "restroom": True, "temple_nearby": True, "pricing_inr_kwh": 16.5,
                    "image_url": "https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=800&q=80"
                },
                "public_visible": True,
                "last_verified_at": datetime.now(timezone.utc)
            },
            {
                "name": "Highway Supercharger - Jodhpur Bypass Plaza",
                "latitude": 27.9450,
                "longitude": 73.2890,
                "address": "NH-62 Bikaner-Jodhpur Bypass, Near Deshnoke Toll, Bikaner",
                "city": "Bikaner",
                "state": "Rajasthan",
                "pincode": "334801",
                "status": ChargingCenterStatus.OPERATIONAL,
                "power_kw": 150.0,
                "contact_phone": "+91 1800 120 4050",
                "operating_hours": "24/7 Open",
                "description": "High-power highway charging hub capable of giving 200km range in 15 minutes. Highway restaurant attached.",
                "connectors": {"CCS2": 4, "Type2": 2, "fast_dc": True},
                "amenities": {
                    "restroom": True, "restaurant": True, "wifi": True, "pricing_inr_kwh": 19.5,
                    "image_url": "https://images.unsplash.com/photo-1558441719-20f5b9d365dc?auto=format&fit=crop&w=800&q=80"
                },
                "public_visible": True,
                "last_verified_at": datetime.now(timezone.utc)
            }
        ]

        for cc in bikaner_stations:
            existing = await db.execute(select(ChargingCenter).where(ChargingCenter.name == cc["name"]))
            center_obj = existing.scalar_one_or_none()
            if not center_obj:
                db.add(ChargingCenter(**cc))
            else:
                for k, v in cc.items():
                    setattr(center_obj, k, v)
        await db.commit()
        print(f"[+] Seeded {len(bikaner_stations)} Bikaner EV Charging Centers.")

        # 3. Seed Bikaner Major Bus Stops
        bikaner_stops_data = [
            {"name": "Beechwal RIICO Hub", "code": "BCH-01", "latitude": 28.0812, "longitude": 73.3754, "city": "Bikaner", "state": "Rajasthan", "address": "NH-15 Beechwal Industrial Area"},
            {"name": "Engineering College Gate", "code": "ECB-02", "latitude": 28.0720, "longitude": 73.3610, "city": "Bikaner", "state": "Rajasthan", "address": "Karni Industrial Bypass"},
            {"name": "Lalgarh Palace & Station", "code": "LGS-03", "latitude": 28.0415, "longitude": 73.3295, "city": "Bikaner", "state": "Rajasthan", "address": "Lalgarh Junction Circle"},
            {"name": "Ambedkar Circle", "code": "AMB-04", "latitude": 28.0260, "longitude": 73.3220, "city": "Bikaner", "state": "Rajasthan", "address": "Court Road, Central Bikaner"},
            {"name": "Junagarh Fort Main Gate", "code": "JNG-05", "latitude": 28.0229, "longitude": 73.3180, "city": "Bikaner", "state": "Rajasthan", "address": "Junagarh Fort Road"},
            {"name": "KEM Road & Kotgate", "code": "KTG-06", "latitude": 28.0160, "longitude": 73.3130, "city": "Bikaner", "state": "Rajasthan", "address": "Old Heritage Market, Kotgate"},
            {"name": "Bikaner Junction Railway Station", "code": "BKN-RLY", "latitude": 28.0190, "longitude": 73.3150, "city": "Bikaner", "state": "Rajasthan", "address": "Station Road Platform 1"},
            {"name": "PBM Hospital Main Gate", "code": "PBM-07", "latitude": 28.0125, "longitude": 73.3250, "city": "Bikaner", "state": "Rajasthan", "address": "Sadul Colony Medical Zone"},
            {"name": "Rani Bazar Overbridge", "code": "RNB-08", "latitude": 28.0090, "longitude": 73.3190, "city": "Bikaner", "state": "Rajasthan", "address": "Rani Bazar Industrial Area Road"},
            {"name": "Tulsi Circle", "code": "TLS-09", "latitude": 28.0150, "longitude": 73.3320, "city": "Bikaner", "state": "Rajasthan", "address": "JNV Colony Main Entry"},
            {"name": "Kanta Khaturia Colony", "code": "KKC-10", "latitude": 28.0080, "longitude": 73.3380, "city": "Bikaner", "state": "Rajasthan", "address": "Near Community Park"},
            {"name": "JNV Colony Sector 3", "code": "JNV-11", "latitude": 28.0020, "longitude": 73.3450, "city": "Bikaner", "state": "Rajasthan", "address": "Major Commercial Center"},
            {"name": "Karni Nagar Stadium", "code": "KRN-12", "latitude": 28.0280, "longitude": 73.3550, "city": "Bikaner", "state": "Rajasthan", "address": "Sports Complex Road"},
            {"name": "Ganga Shahar Bus Stand", "code": "GSH-13", "latitude": 27.9860, "longitude": 73.3010, "city": "Bikaner", "state": "Rajasthan", "address": "Main Bazar, Ganga Shahar"},
            {"name": "Bhinasar Circle", "code": "BHN-14", "latitude": 27.9750, "longitude": 73.2950, "city": "Bikaner", "state": "Rajasthan", "address": "Nokha Road Junction"},
            {"name": "Deshnoke Karni Mata Stand", "code": "DSH-15", "latitude": 27.7950, "longitude": 73.3450, "city": "Bikaner", "state": "Rajasthan", "address": "Temple Main Road, Deshnoke"}
        ]

        stops_map = {}
        for s_data in bikaner_stops_data:
            existing = await db.execute(select(Stop).where(Stop.name == s_data["name"]))
            stop_obj = existing.scalar_one_or_none()
            if not stop_obj:
                stop_obj = Stop(**s_data)
                db.add(stop_obj)
                await db.flush()
            stops_map[s_data["name"]] = stop_obj
        await db.commit()
        print(f"[+] Seeded {len(bikaner_stops_data)} Bikaner Bus Stops.")

        # 4. Seed Bikaner Transit Routes (Where Is My Urja)
        routes_data = [
            {
                "name": "Line 1 (Red E-Line): Beechwal RIICO ⇄ Ganga Shahar",
                "code": "BKN-L1",
                "city": "Bikaner",
                "state": "Rajasthan",
                "description": "High frequency North-South E-Bus corridor passing via Junagarh Fort, KEM Road, and PBM Hospital.",
                "color": "#ef4444",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [73.3754, 28.0812], [73.3685, 28.0770], [73.3610, 28.0720], [73.3480, 28.0600],
                        [73.3380, 28.0500], [73.3295, 28.0415], [73.3235, 28.0320], [73.3180, 28.0229],
                        [73.3155, 28.0195], [73.3130, 28.0160], [73.3190, 28.0145], [73.3250, 28.0125],
                        [73.3220, 28.0105], [73.3190, 28.0090], [73.3100, 27.9980], [73.3010, 27.9860]
                    ]
                },
                "stops": [
                    "Beechwal RIICO Hub", "Engineering College Gate", "Lalgarh Palace & Station",
                    "Junagarh Fort Main Gate", "KEM Road & Kotgate", "PBM Hospital Main Gate",
                    "Rani Bazar Overbridge", "Ganga Shahar Bus Stand"
                ]
            },
            {
                "name": "Line 2 (Green E-Line): Railway Station ⇄ Karni Stadium",
                "code": "BKN-L2",
                "city": "Bikaner",
                "state": "Rajasthan",
                "description": "Express electric transit linking Bikaner Junction, Ambedkar Circle, JNV Colony, and Karni Nagar Stadium.",
                "color": "#10b981",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [73.3150, 28.0190], [73.3185, 28.0225], [73.3220, 28.0260], [73.3200, 28.0245],
                        [73.3180, 28.0229], [73.3250, 28.0190], [73.3320, 28.0150], [73.3350, 28.0115],
                        [73.3380, 28.0080], [73.3415, 28.0050], [73.3450, 28.0020], [73.3500, 28.0150],
                        [73.3550, 28.0280]
                    ]
                },
                "stops": [
                    "Bikaner Junction Railway Station", "Ambedkar Circle", "Junagarh Fort Main Gate",
                    "Tulsi Circle", "Kanta Khaturia Colony", "JNV Colony Sector 3", "Karni Nagar Stadium"
                ]
            },
            {
                "name": "Line 3 (Blue E-Line): PBM Medical Hub ⇄ Deshnoke Temple",
                "code": "BKN-L3",
                "city": "Bikaner",
                "state": "Rajasthan",
                "description": "Pilgrim and medical transit connecting PBM Hospital, Rani Bazar, Bhinasar, and Deshnoke Temple.",
                "color": "#0ea5e9",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [73.3250, 28.0125], [73.3220, 28.0105], [73.3190, 28.0090], [73.3100, 27.9980],
                        [73.3010, 27.9860], [73.2980, 27.9805], [73.2950, 27.9750], [73.3050, 27.9300],
                        [73.3200, 27.8800], [73.3350, 27.8300], [73.3450, 27.7950]
                    ]
                },
                "stops": [
                    "PBM Hospital Main Gate", "Rani Bazar Overbridge", "Ganga Shahar Bus Stand",
                    "Bhinasar Circle", "Deshnoke Karni Mata Stand"
                ]
            },
            {
                "name": "Line 4 (Yellow E-Line): Lalgarh ⇄ JNV Tech Corridor",
                "code": "BKN-L4",
                "city": "Bikaner",
                "state": "Rajasthan",
                "description": "Connecting Lalgarh Junction, Ambedkar Circle, PBM Hospital, and JNV Colony.",
                "color": "#f59e0b",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [73.3295, 28.0415], [73.3260, 28.0340], [73.3220, 28.0260], [73.3200, 28.0245],
                        [73.3180, 28.0229], [73.3215, 28.0180], [73.3250, 28.0125], [73.3285, 28.0138],
                        [73.3320, 28.0150], [73.3385, 28.0085], [73.3450, 28.0020]
                    ]
                },
                "stops": [
                    "Lalgarh Palace & Station", "Ambedkar Circle", "Junagarh Fort Main Gate",
                    "PBM Hospital Main Gate", "Tulsi Circle", "JNV Colony Sector 3"
                ]
            }
        ]

        for r_info in routes_data:
            existing = await db.execute(select(Route).where(Route.code == r_info["code"]))
            route_obj = existing.scalar_one_or_none()
            if not route_obj:
                route_obj = Route(
                    name=r_info["name"],
                    code=r_info["code"],
                    city=r_info["city"],
                    state=r_info["state"],
                    description=r_info["description"],
                    color=r_info["color"],
                    geometry=r_info.get("geometry")
                )
                db.add(route_obj)
                await db.flush()
            else:
                route_obj.geometry = r_info.get("geometry")
                route_obj.color = r_info["color"]
                await db.flush()

            # Add Route Stops
            for seq, stop_name in enumerate(r_info["stops"]):
                stop_obj = stops_map.get(stop_name)
                if stop_obj:
                    existing_rs = await db.execute(
                        select(RouteStop).where(RouteStop.route_id == route_obj.id, RouteStop.stop_id == stop_obj.id)
                    )
                    if not existing_rs.scalar_one_or_none():
                        db.add(RouteStop(
                            route_id=route_obj.id,
                            stop_id=stop_obj.id,
                            sequence=seq + 1,
                            distance_from_start_km=round((seq + 1) * 2.4, 1)
                        ))
        await db.commit()
        print(f"[+] Seeded {len(routes_data)} Bikaner Routes and Stop Associations.")

        # 5. Seed Public Transit Department & Electric Buses
        from app.models.department import Department
        from app.models.telemetry import TelemetryLatest

        dept_query = await db.execute(select(Department).where(Department.code == "TRANSIT_BKN"))
        dept = dept_query.scalar_one_or_none()
        if not dept:
            dept = Department(
                name="Bikaner Municipal E-Transit",
                code="TRANSIT_BKN",
                description="Public electric bus and transit services for Bikaner city",
                is_active=True
            )
            db.add(dept)
            await db.flush()

        buses_seed = [
            {
                "code": "BUS-101", "type": VehicleType.ELECTRIC_BUS, "make": "Olectra", "model": "K9 E-Bus",
                "route_code": "BKN-L1", "lat": 28.0229, "lng": 73.3180, "speed": 34.0, "heading": 175.0, "soc": 82.0
            },
            {
                "code": "BUS-102", "type": VehicleType.ELECTRIC_BUS, "make": "Tata Motors", "model": "Ultra EV 9m",
                "route_code": "BKN-L1", "lat": 28.0720, "lng": 73.3610, "speed": 42.0, "heading": 355.0, "soc": 68.0
            },
            {
                "code": "BUS-201", "type": VehicleType.ELECTRIC_BUS, "make": "JBM", "model": "Ecolife 12m",
                "route_code": "BKN-L2", "lat": 28.0150, "lng": 73.3320, "speed": 28.0, "heading": 85.0, "soc": 91.0
            },
            {
                "code": "BUS-301", "type": VehicleType.ELECTRIC_BUS, "make": "Switch Mobility", "model": "EiV 12",
                "route_code": "BKN-L3", "lat": 27.9750, "lng": 73.2950, "speed": 48.0, "heading": 180.0, "soc": 74.0
            },
            {
                "code": "BUS-401", "type": VehicleType.ELECTRIC_BUS, "make": "Olectra", "model": "CX2 E-Coach",
                "route_code": "BKN-L4", "lat": 28.0260, "lng": 73.3220, "speed": 31.0, "heading": 90.0, "soc": 88.0
            }
        ]

        for b in buses_seed:
            v_res = await db.execute(select(Vehicle).where(Vehicle.vehicle_code == b["code"]))
            v_obj = v_res.scalar_one_or_none()
            if not v_obj:
                v_obj = Vehicle(
                    vehicle_code=b["code"],
                    registration_number=f"RJ-07-EV-{b['code'].split('-')[1]}",
                    vehicle_type=b["type"],
                    make=b["make"],
                    model=b["model"],
                    year=2024,
                    department_id=dept.id,
                    is_active=True,
                    public_visible=True
                )
                db.add(v_obj)
                await db.flush()

            # Telemetry Latest
            t_res = await db.execute(select(TelemetryLatest).where(TelemetryLatest.vehicle_id == v_obj.id))
            t_obj = t_res.scalar_one_or_none()
            if not t_obj:
                t_obj = TelemetryLatest(
                    vehicle_id=v_obj.id,
                    latitude=b["lat"],
                    longitude=b["lng"],
                    speed_kph=b["speed"],
                    heading_deg=b["heading"],
                    soc_pct=b["soc"],
                    charging=False,
                    connectivity_status="online",
                    last_seen=datetime.now(timezone.utc)
                )
                db.add(t_obj)
            else:
                t_obj.latitude = b["lat"]
                t_obj.longitude = b["lng"]
                t_obj.speed_kph = b["speed"]
                t_obj.heading_deg = b["heading"]
                t_obj.soc_pct = b["soc"]
                t_obj.last_seen = datetime.now(timezone.utc)

            # Link Route
            r_query = await db.execute(select(Route).where(Route.code == b["route_code"]))
            r_obj = r_query.scalar_one_or_none()
            if r_obj:
                vr_res = await db.execute(select(VehicleRoute).where(VehicleRoute.vehicle_id == v_obj.id))
                vr_obj = vr_res.scalar_one_or_none()
                if not vr_obj:
                    vr_obj = VehicleRoute(
                        vehicle_id=v_obj.id,
                        route_id=r_obj.id,
                        is_active=True,
                        direction="Inbound"
                    )
                    db.add(vr_obj)
                else:
                    vr_obj.route_id = r_obj.id
                    vr_obj.is_active = True

        await db.commit()
        print("[+] Seeded Public Transit Electric Buses and Route Assignments.")

        # 6. Seed Help & Emergency Contacts for Bikaner
        help_contacts = [
            {"city": "Bikaner", "state": "Rajasthan", "department": "Bikaner E-Bus Transit Helpline", "category": "transport", "phone": "+91 151 222 6600", "availability": "06:00 AM - 11:00 PM", "description": "Official RSRTC & Bikaner Municipal E-Bus route enquiry and lost & found desk."},
            {"city": "Bikaner", "state": "Rajasthan", "department": "Rajasthan EV Charging Emergency Support", "category": "charging_support", "phone": "1800 180 6127", "availability": "24/7 Available", "description": "Statewide 24/7 on-road EV battery assistance, towing, and station outage reporting."},
            {"city": "Bikaner", "state": "Rajasthan", "department": "PBM Hospital Trauma & Ambulance Hub", "category": "emergency", "phone": "+91 151 222 6300", "availability": "24/7 Emergency", "description": "Direct emergency response and EV Ambulance dispatch unit at PBM Hospital Bikaner."},
            {"city": "Bikaner", "state": "Rajasthan", "department": "Bikaner Traffic Police Control Room", "category": "emergency", "phone": "112 / +91 151 222 6100", "availability": "24/7 Emergency", "description": "Traffic updates, road clearance, and emergency transit assistance."}
        ]

        for hc in help_contacts:
            existing = await db.execute(select(HelpContact).where(HelpContact.department == hc["department"]))
            if not existing.scalar_one_or_none():
                db.add(HelpContact(**hc))
        await db.commit()
        print(f"[+] Seeded {len(help_contacts)} Bikaner Help Contacts.")

        print("[SUCCESS] Database seeding for Bikaner EV Platform completed successfully!")

if __name__ == "__main__":
    asyncio.run(seed())

