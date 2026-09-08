import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://neondb_owner:npg_5GdRaXnAlBx1@ep-old-field-aerihoyo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
)

def run_seed():
    print("=" * 60)
    print("ChargeEase Database Remediation and Seeding Script")
    print("=" * 60)

    conn = psycopg2.connect(DATABASE_URL, connect_timeout=15)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. Fix Charging Centers with NULL City
    print("\n[1] Updating Charging Centers with missing city/state...")
    cur.execute("""
        UPDATE charging_centers
        SET city = 'Delhi', state = 'Delhi'
        WHERE city IS NULL;
    """)
    updated_cc = cur.rowcount
    print(f"    -> Updated {updated_cc} charging centers with city='Delhi'.")

    # 2. Check/Add Bikaner Municipal E-Transit Department
    print("\n[2] Verifying Bikaner Department...")
    cur.execute("SELECT id, name FROM departments WHERE code = 'BIKANER_TRANSIT' OR name ILIKE '%Bikaner%';")
    bikaner_dept = cur.fetchone()
    if not bikaner_dept:
        dept_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO departments (id, name, code, description, created_at, updated_at)
            VALUES (%s, 'Bikaner Municipal E-Transit', 'BIKANER_TRANSIT', 'Bikaner Municipal Corporation EV Bus Transit Fleet', now(), now())
            RETURNING id, name;
        """, (dept_id,))
        bikaner_dept = cur.fetchone()
        print(f"    -> Created Bikaner Department: {bikaner_dept['name']} ({bikaner_dept['id']})")
    else:
        print(f"    -> Found Bikaner Department: {bikaner_dept['name']} ({bikaner_dept['id']})")

    bikaner_dept_id = bikaner_dept["id"]

    # 3. Add Bikaner Transit Operator Account
    print("\n[3] Seeding Bikaner Transit Operator User...")
    cur.execute("SELECT id, email FROM users WHERE email = 'bikaner.transit@chargeease.gov';")
    bkn_user = cur.fetchone()
    if not bkn_user:
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        from app.core.security import hash_password
        hashed = hash_password("bikaner123")
        u_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO users (id, email, hashed_password, full_name, role, department_id, is_active, created_at, updated_at)
            VALUES (%s, 'bikaner.transit@chargeease.gov', %s, 'Bikaner Transit Fleet Dispatcher', 'DEPARTMENT_ADMIN', %s, true, now(), now())
            RETURNING id, email;
        """, (u_id, hashed, bikaner_dept_id))
        bkn_user = cur.fetchone()
        print(f"    -> Created User: {bkn_user['email']} (password: bikaner123)")
    else:
        print(f"    -> User already exists: {bkn_user['email']}")

    # 4. Add Bikaner Geofences
    print("\n[4] Seeding Bikaner Geofences...")
    geofences_to_add = [
        ("Karni Industrial Area E-Bus Depot", "DEPOT", bikaner_dept_id, 28.0581, 73.3421, 350.0),
        ("Rani Bazar Transit Terminal Depot", "DEPOT", bikaner_dept_id, 28.0094, 73.3195, 250.0),
        ("PBM Hospital EV Transit Zone", "STATION", bikaner_dept_id, 28.0128, 73.3256, 200.0),
    ]
    for g_name, g_type, dept_id, lat, lng, rad in geofences_to_add:
        cur.execute("SELECT id FROM geofences WHERE name = %s;", (g_name,))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO geofences (id, name, geofence_type, department_id, center_lat, center_lng, radius_m, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, true, now(), now());
            """, (str(uuid.uuid4()), g_name, g_type, dept_id, lat, lng, rad))
            print(f"    -> Added Geofence: {g_name}")
        else:
            print(f"    -> Geofence exists: {g_name}")

    # 5. Seed Realistic Trips
    print("\n[5] Seeding Vehicle Trips...")
    cur.execute("SELECT count(*) as cnt FROM trips;")
    trip_count = cur.fetchone()["cnt"]
    print(f"    -> Current trips count: {trip_count}")

    if trip_count == 0:
        cur.execute("SELECT id, vehicle_code, vehicle_type FROM vehicles;")
        vehicles = cur.fetchall()
        print(f"    -> Seeding trips across {len(vehicles)} vehicles...")

        now = datetime.now(timezone.utc)

        sample_trips = []
        for v in vehicles:
            v_id = v["id"]
            code = v["vehicle_code"]
            is_bikaner = "BUS-" in code.upper()

            if is_bikaner:
                base_lat, base_lng = 28.0229, 73.3180
                dest_lat, dest_lng = 28.0094, 73.3195
            else:
                base_lat, base_lng = 28.6517, 77.1935
                dest_lat, dest_lng = 28.5491, 77.2533

            t1_start = now - timedelta(days=1, hours=4)
            t1_end = t1_start + timedelta(minutes=48)
            sample_trips.append((
                str(uuid.uuid4()), v_id, t1_start, t1_end,
                base_lat, base_lng, dest_lat, dest_lng,
                18.4, 94.0, 72.0, 14.8, "COMPLETED"
            ))

            t2_start = now - timedelta(hours=3)
            t2_end = t2_start + timedelta(minutes=35)
            sample_trips.append((
                str(uuid.uuid4()), v_id, t2_start, t2_end,
                dest_lat, dest_lng, base_lat + 0.015, base_lng + 0.012,
                14.2, 88.0, 71.0, 11.5, "COMPLETED"
            ))

            if code in ["bus-001", "BUS-101", "fire-001"]:
                t3_start = now - timedelta(minutes=18)
                sample_trips.append((
                    str(uuid.uuid4()), v_id, t3_start, None,
                    base_lat, base_lng, None, None,
                    6.8, 85.0, 79.0, 4.2, "ACTIVE"
                ))

        for t in sample_trips:
            cur.execute("""
                INSERT INTO trips (
                    id, vehicle_id, started_at, ended_at,
                    start_lat, start_lng, end_lat, end_lng,
                    distance_km, start_soc, end_soc, energy_consumed_kwh,
                    status, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, now(), now()
                );
            """, t)

        print(f"    -> Successfully inserted {len(sample_trips)} realistic trips!")

    conn.commit()
    print("\n[6] Committed all database remediations successfully!")

    print("\n" + "=" * 60)
    print("FINAL DATABASE VERIFICATION COUNTS:")
    print("=" * 60)
    for table in ["departments", "users", "vehicles", "charging_centers", "geofences", "trips", "routes", "stops"]:
        cur.execute(f"SELECT count(*) as cnt FROM {table};")
        cnt = cur.fetchone()["cnt"]
        print(f"  {table:20s}: {cnt}")

    cur.execute("SELECT count(*) as cnt FROM charging_centers WHERE city IS NULL;")
    null_cities = cur.fetchone()["cnt"]
    print(f"  Charging centers with NULL city: {null_cities}")

    cur.close()
    conn.close()
    print("\nDatabase remediation complete.")

if __name__ == "__main__":
    run_seed()
