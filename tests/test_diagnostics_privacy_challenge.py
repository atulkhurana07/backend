import pytest
import uuid
from datetime import datetime, timezone
from tests.conftest import make_auth_header
from tests.test_telemetry import make_telemetry_payload
from app.models.vehicle import Vehicle, VehicleType
from app.models.device import Device, DeviceStatus


class TestDiagnosticsAndPrivacyChallenge:
    """
    Empirical Challenge Test Suite for Milestone 1:
    1. Operator endpoints (/api/operator/vehicles, /api/operator/vehicles/{id})
       - Null telemetry
       - Missing diagnostics (omitted / None)
       - Boundary temperatures (-40°C, 0.0°C, 85.5°C, 37.125°C)
       - Multiple / empty / complex DTCs
       - Cross-department isolation & unauthenticated access
    2. Public endpoints (/api/public/vehicles, /api/public/vehicles/{id})
       - Rigorous stripping of battery_temp_c, dtcs, and sensitive fields
       - Public visibility & active status filtering
    """

    # -------------------------------------------------------------------------
    # 1. Operator Endpoints: Null Telemetry & Missing Diagnostics
    # -------------------------------------------------------------------------

    async def test_operator_vehicles_null_telemetry(self, client, users, vehicles):
        """
        Challenge: Vehicle exists in database but has received zero telemetry events.
        Endpoints must return 200 with null values for all telemetry and diagnostic fields,
        without throwing NullPointerException, AttributeError, or 500 error.
        """
        headers = make_auth_header(users["transport_admin"])
        resp = await client.get("/api/operator/vehicles", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()

        bus = vehicles["bus"]
        bus_entry = next((v for v in data if v["id"] == str(bus.id)), None)
        assert bus_entry is not None, "Vehicle bus-test-001 should be present in operator list"
        
        # Telemetry and diagnostics should be gracefully None
        assert bus_entry["latitude"] is None
        assert bus_entry["longitude"] is None
        assert bus_entry["speed_kph"] is None
        assert bus_entry["soc_pct"] is None
        assert bus_entry["battery_temp_c"] is None
        assert bus_entry["dtcs"] is None
        assert bus_entry["last_seen"] is None

    async def test_operator_vehicle_by_id_null_telemetry(self, client, users, vehicles):
        """
        Challenge: GET /api/operator/vehicles/{id} for a vehicle with no telemetry records.
        """
        bus = vehicles["bus"]
        headers = make_auth_header(users["transport_admin"])
        resp = await client.get(f"/api/operator/vehicles/{bus.id}", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()

        assert data["id"] == str(bus.id)
        assert data["vehicle_code"] == bus.vehicle_code
        assert data["battery_temp_c"] is None
        assert data["dtcs"] is None
        assert data["latitude"] is None
        assert data["soc_pct"] is None

    async def test_operator_endpoints_missing_diagnostics_payload(
        self, client, users, vehicles, devices
    ):
        """
        Challenge: Telemetry ingested with location/energy but diagnostics key omitted.
        Both operator endpoints must return valid telemetry while battery_temp_c and dtcs remain None.
        """
        bus = vehicles["bus"]
        # Ingest payload with no diagnostics dict
        payload = make_telemetry_payload(
            device_id=devices["bus_device"].device_code,
            vehicle_id=bus.vehicle_code,
            location={"lat": 28.6139, "lng": 77.2090, "accuracy_m": 5},
            motion={"speed_kph": 30.0, "heading_deg": 90.0},
            energy={"soc_pct": 80.0, "estimated_range_km": 150.0, "charging": False},
            diagnostics=None,
        )
        ingest_resp = await client.post("/api/ingest/telemetry", json=payload)
        assert ingest_resp.status_code == 200

        headers = make_auth_header(users["transport_admin"])
        
        # Test list endpoint
        resp_list = await client.get("/api/operator/vehicles", headers=headers)
        assert resp_list.status_code == 200
        bus_entry = next(v for v in resp_list.json() if v["id"] == str(bus.id))
        assert bus_entry["soc_pct"] == 80.0
        assert bus_entry["speed_kph"] == 30.0
        assert bus_entry["battery_temp_c"] is None
        assert bus_entry["dtcs"] is None

        # Test detail endpoint
        resp_detail = await client.get(f"/api/operator/vehicles/{bus.id}", headers=headers)
        assert resp_detail.status_code == 200
        detail_data = resp_detail.json()
        assert detail_data["soc_pct"] == 80.0
        assert detail_data["battery_temp_c"] is None
        assert detail_data["dtcs"] is None

    # -------------------------------------------------------------------------
    # 2. Operator Endpoints: Boundary Temperatures
    # -------------------------------------------------------------------------

    async def test_operator_boundary_battery_temperatures_comprehensive(
        self, client, users, vehicles, devices
    ):
        """
        Challenge: Boundary temperatures including:
        - Arctic extreme: -40.0°C
        - Sub-zero fractional: -0.5°C
        - Freezing point / falsy zero check: 0.0°C (must not coerce to None)
        - Nominal ambient: 25.0°C
        - High warning threshold: 45.5°C
        - Thermal runaway extreme: 85.5°C
        - Multi-decimal precision: 37.125°C
        Verify float precision and that 0.0 is preserved across consecutive updates.
        """
        bus = vehicles["bus"]
        headers = make_auth_header(users["transport_admin"])

        test_cases = [
            -40.0,
            -0.5,
            0.0,
            25.0,
            45.5,
            85.5,
            37.125,
        ]

        for idx, temp in enumerate(test_cases):
            # Ingest payload with advancing sequence and unique event_id
            payload = make_telemetry_payload(
                device_id=devices["bus_device"].device_code,
                vehicle_id=bus.vehicle_code,
                event_id=str(uuid.uuid4()),
                seq=idx + 1,
                diagnostics={"battery_temp_c": temp, "dtcs": []},
            )
            ingest_resp = await client.post("/api/ingest/telemetry", json=payload)
            assert ingest_resp.status_code == 200, f"Ingest failed for temp {temp}"

            # Check detail endpoint
            resp_detail = await client.get(f"/api/operator/vehicles/{bus.id}", headers=headers)
            assert resp_detail.status_code == 200
            detail_data = resp_detail.json()
            assert detail_data["battery_temp_c"] == temp, (
                f"Detail API: Expected battery_temp_c={temp}, got {detail_data['battery_temp_c']}"
            )

            # Check list endpoint
            resp_list = await client.get("/api/operator/vehicles", headers=headers)
            assert resp_list.status_code == 200
            target = next(v for v in resp_list.json() if v["id"] == str(bus.id))
            assert target["battery_temp_c"] == temp, (
                f"List API: Expected battery_temp_c={temp}, got {target['battery_temp_c']}"
            )

    # -------------------------------------------------------------------------
    # 3. Operator Endpoints: Multiple & Edge-Case DTCs
    # -------------------------------------------------------------------------

    async def test_operator_empty_dtcs_list(self, client, users, vehicles, devices):
        """
        Challenge: Vehicle with empty DTC list [].
        Should preserve empty list [] and not convert to None or fail.
        """
        bus = vehicles["bus"]
        payload = make_telemetry_payload(
            device_id=devices["bus_device"].device_code,
            vehicle_id=bus.vehicle_code,
            diagnostics={"battery_temp_c": 32.0, "dtcs": []},
        )
        await client.post("/api/ingest/telemetry", json=payload)

        headers = make_auth_header(users["transport_admin"])
        resp = await client.get(f"/api/operator/vehicles/{bus.id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["dtcs"] == []

    async def test_operator_multiple_and_complex_dtcs(
        self, client, users, vehicles, devices
    ):
        """
        Challenge: Vehicle reporting multiple complex Diagnostic Trouble Codes.
        Verify full list preservation, ordering, and special characters.
        """
        bus = vehicles["bus"]
        dtc_list = [
            "P0A80",          # Replace Hybrid/EV Battery Pack
            "P0A7F",          # Hybrid/EV Battery Pack Deterioration
            "P0100",          # Mass Airflow Sensor
            "B1000-01",       # Body control fault with sub-code
            "U0100:87",       # CAN communication timeout
            "CUSTOM_FAULT_X", # Manufacturer custom string
        ]
        payload = make_telemetry_payload(
            device_id=devices["bus_device"].device_code,
            vehicle_id=bus.vehicle_code,
            diagnostics={"battery_temp_c": 52.0, "dtcs": dtc_list},
        )
        ingest_resp = await client.post("/api/ingest/telemetry", json=payload)
        assert ingest_resp.status_code == 200

        headers = make_auth_header(users["transport_admin"])
        resp = await client.get(f"/api/operator/vehicles/{bus.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["dtcs"] == dtc_list
        assert len(data["dtcs"]) == 6

        # Also verify via list endpoint
        resp_list = await client.get("/api/operator/vehicles", headers=headers)
        assert resp_list.status_code == 200
        target = next(v for v in resp_list.json() if v["id"] == str(bus.id))
        assert target["dtcs"] == dtc_list

    # -------------------------------------------------------------------------
    # 4. Operator Authorization & Isolation Challenge
    # -------------------------------------------------------------------------

    async def test_operator_unauthenticated_rejected(self, client, vehicles):
        """Challenge: Unauthenticated access to operator endpoints must be rejected (401 or 403)."""
        resp_list = await client.get("/api/operator/vehicles")
        assert resp_list.status_code in (401, 403)

        bus = vehicles["bus"]
        resp_detail = await client.get(f"/api/operator/vehicles/{bus.id}")
        assert resp_detail.status_code in (401, 403)

    async def test_operator_cross_department_isolation(self, client, users, vehicles):
        """
        Challenge: Fire department admin cannot access Transport department vehicle diagnostics.
        Must return 404 (or not found in list) to prevent diagnostic leaks across departments.
        """
        bus = vehicles["bus"]  # Belongs to Transport department
        fire_headers = make_auth_header(users["fire_admin"])

        # Detail endpoint should deny access
        resp_detail = await client.get(f"/api/operator/vehicles/{bus.id}", headers=fire_headers)
        assert resp_detail.status_code == 404

        # List endpoint should not contain bus
        resp_list = await client.get("/api/operator/vehicles", headers=fire_headers)
        assert resp_list.status_code == 200
        vehicle_ids = [v["id"] for v in resp_list.json()]
        assert str(bus.id) not in vehicle_ids

    # -------------------------------------------------------------------------
    # 5. Public API Privacy Boundaries: Strict Stripping of Diagnostics
    # -------------------------------------------------------------------------

    async def test_public_vehicles_strictly_strips_diagnostics(
        self, client, vehicles, devices
    ):
        """
        Challenge: Ingest sensitive hardware diagnostics (severe battery temp and critical DTCs).
        Query GET /api/public/vehicles without authentication.
        Rigorous assertion: 'battery_temp_c', 'dtcs', 'device_id', 'device_code',
        and 'registration_number' must NEVER appear in the public payload.
        """
        bus = vehicles["bus"]
        sensitive_payload = make_telemetry_payload(
            device_id=devices["bus_device"].device_code,
            vehicle_id=bus.vehicle_code,
            location={"lat": 28.6139, "lng": 77.2090, "accuracy_m": 4},
            motion={"speed_kph": 45.0, "heading_deg": 180.0},
            energy={"soc_pct": 55.0, "estimated_range_km": 110.0, "charging": False},
            diagnostics={
                "battery_temp_c": 62.4,
                "dtcs": ["P0A80", "FIRE_ALERT_CRITICAL", "THERMAL_RUNAWAY"],
            },
        )
        ingest_resp = await client.post("/api/ingest/telemetry", json=sensitive_payload)
        assert ingest_resp.status_code == 200

        # Query public vehicle list
        resp = await client.get("/api/public/vehicles")
        assert resp.status_code == 200
        vehicles_data = resp.json()
        assert len(vehicles_data) >= 1

        target_vehicle = next((v for v in vehicles_data if v["id"] == str(bus.id)), None)
        assert target_vehicle is not None, "Target public vehicle should be present"

        # Explicit forbidden keys check
        forbidden_keys = [
            "battery_temp_c",
            "dtcs",
            "dtc",
            "registration_number",
            "device_id",
            "device_code",
            "driver_name",
            "driver_phone",
            "firmware",
            "raw_payload",
        ]
        for key in forbidden_keys:
            assert key not in target_vehicle, f"Privacy violation: '{key}' found in public vehicle response"

        # Ensure valid public fields are present and uncorrupted
        assert target_vehicle["vehicle_code"] == bus.vehicle_code
        assert target_vehicle["vehicle_type"] == bus.vehicle_type.value
        assert target_vehicle["latitude"] == round(28.6139, 6)
        assert target_vehicle["longitude"] == round(77.2090, 6)
        assert target_vehicle["speed_kph"] == 45
        assert target_vehicle["soc_pct"] == 55

    async def test_public_vehicle_by_id_strictly_strips_diagnostics(
        self, client, vehicles, devices
    ):
        """
        Challenge: Query GET /api/public/vehicles/{id} for vehicle with sensitive diagnostics.
        Ensure battery_temp_c and dtcs are absent.
        """
        bus = vehicles["bus"]
        sensitive_payload = make_telemetry_payload(
            device_id=devices["bus_device"].device_code,
            vehicle_id=bus.vehicle_code,
            diagnostics={"battery_temp_c": 58.9, "dtcs": ["P0A80"]},
        )
        await client.post("/api/ingest/telemetry", json=sensitive_payload)

        resp = await client.get(f"/api/public/vehicles/{bus.id}")
        assert resp.status_code == 200
        data = resp.json()

        assert data["id"] == str(bus.id)
        assert "battery_temp_c" not in data, "Privacy violation: battery_temp_c in public single-vehicle response"
        assert "dtcs" not in data, "Privacy violation: dtcs in public single-vehicle response"
        assert "registration_number" not in data

    async def test_public_endpoints_respect_visibility_flags(
        self, client, db_session, departments
    ):
        """
        Challenge: Non-public (public_visible=False) and inactive (is_active=False) vehicles
        must never leak via public endpoints.
        """
        # Create private vehicle
        secret_vehicle = Vehicle(
            vehicle_code="secret-vip-001",
            vehicle_type=VehicleType.UTILITY_EV,
            department_id=departments["transport"].id,
            make="Tata",
            model="Nexon EV",
            year=2024,
            is_active=True,
            public_visible=False,
        )
        # Create inactive vehicle
        decommissioned_vehicle = Vehicle(
            vehicle_code="decomm-bus-999",
            vehicle_type=VehicleType.ELECTRIC_BUS,
            department_id=departments["transport"].id,
            make="Tata",
            model="Starbus",
            year=2020,
            is_active=False,
            public_visible=True,
        )
        db_session.add_all([secret_vehicle, decommissioned_vehicle])
        await db_session.commit()
        await db_session.refresh(secret_vehicle)
        await db_session.refresh(decommissioned_vehicle)

        # Public list query
        resp_list = await client.get("/api/public/vehicles")
        assert resp_list.status_code == 200
        public_ids = [v["id"] for v in resp_list.json()]

        assert str(secret_vehicle.id) not in public_ids, "Private vehicle leaked in public list"
        assert str(decommissioned_vehicle.id) not in public_ids, "Inactive vehicle leaked in public list"

        # Public detail queries
        resp_secret = await client.get(f"/api/public/vehicles/{secret_vehicle.id}")
        assert resp_secret.status_code == 404, "Private vehicle accessible via public detail endpoint"

        resp_decomm = await client.get(f"/api/public/vehicles/{decommissioned_vehicle.id}")
        assert resp_decomm.status_code == 404, "Inactive vehicle accessible via public detail endpoint"
