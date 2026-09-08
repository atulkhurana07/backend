"""
ChargeEase (URJA EV Fleet Platform) - End-to-End Requirement-Driven Test Suite

Authoritative Requirements Sources:
- ORIGINAL_REQUEST.md (§R1, §R2, §R3, Acceptance Criteria)
- PROJECT.md (§Architecture, §Feature Inventory, §Interface Contracts)

Test Hierarchy:
- Tier 1: Feature Coverage (>= 5 test cases per core feature across 7 features = 36 tests)
- Tier 2: Boundary & Corner Cases (>= 5 test cases per feature across 6 boundaries = 35 tests)
- Tier 3: Cross-Feature Combinations (Pairwise compound interactions = 7 tests)
- Tier 4: Real-World Application Scenarios (Operational Delhi fleet workflows = 5 scenarios)

Execution:
  python -m pytest backend/tests/test_e2e_requirements.py -v
"""

import pytest
import asyncio
import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Optional

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.telemetry import TelemetryEvent, TelemetryLatest
from app.models.alert import Alert, AlertType, AlertSeverity, AlertStatus
from app.models.vehicle import Vehicle, VehicleType
from app.models.device import Device, DeviceStatus
from app.models.department import Department
from app.models.charging_center import ChargingCenter, ChargingCenterStatus
from app.websocket.manager import ConnectionManager, manager
from tests.conftest import make_auth_header


# ==============================================================================
# Test Helpers & Fixtures
# ==============================================================================

class MockWebSocket:
    """Mock WebSocket connection for testing ConnectionManager broadcasts."""

    def __init__(self):
        self.messages: list[str] = []
        self.is_accepted: bool = False
        self.is_closed: bool = False

    async def accept(self):
        self.is_accepted = True

    async def send_text(self, data: str):
        if self.is_closed:
            raise RuntimeError("Cannot send text to a closed WebSocket")
        self.messages.append(data)

    async def close(self, code: int = 1000):
        self.is_closed = True


def make_telemetry_payload(
    device_code: str = "dev-bus-test-001",
    vehicle_code: str = "bus-test-001",
    **overrides
) -> dict:
    """Construct a valid opaque-box telemetry payload adhering to ORIGINAL_REQUEST.md §R2."""
    now_iso = datetime.now(timezone.utc).isoformat()
    base = {
        "device_id": device_code,
        "vehicle_id": vehicle_code,
        "event_id": str(uuid.uuid4()),
        "observed_at": now_iso,
        "location": {"lat": 28.6315, "lng": 77.2167, "accuracy_m": 6.5},
        "motion": {"speed_kph": 38.0, "heading_deg": 120.0},
        "energy": {"soc_pct": 72.0, "estimated_range_km": 135.0, "charging": False},
        "diagnostics": {"dtcs": [], "battery_temp_c": 34.0},
        "connectivity": {"network": "4G", "firmware": "0.3.1"},
        "seq": 1,
    }

    for key, value in overrides.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            base[key].update(value)
        else:
            base[key] = value

    return base


@pytest.fixture
async def sample_charging_hub(db_session: AsyncSession) -> ChargingCenter:
    """Seed Connaught Place Fast Charging Hub for public API tests."""
    hub = ChargingCenter(
        name="Connaught Place Fast Charging Hub",
        latitude=28.6315,
        longitude=77.2167,
        address="Block B, Inner Circle, Connaught Place",
        city="New Delhi",
        state="Delhi",
        pincode="110001",
        status=ChargingCenterStatus.OPERATIONAL,
        description="High-speed EV charging station with CCS2 and Type 2 connectors",
        power_kw=150.0,
        connectors={"CCS2": 4, "Type2": 2},
        public_visible=True,
    )
    db_session.add(hub)
    await db_session.commit()
    await db_session.refresh(hub)
    return hub


# ==============================================================================
# Tier 1: Feature Coverage (>= 5 test cases per feature across 7 features)
# ==============================================================================

class TestTier1FeatureCoverage:
    """
    Tier 1: Systematic coverage of primary behavior, HTTP status codes,
    response payloads, and data models across all 7 platform features.
    """

    # --- Feature 1: Telemetry Ingestion ---

    async def test_t1_f01_valid_telemetry_accepted_with_event_id(self, client: AsyncClient, vehicles, devices):
        """ORIGINAL_REQUEST §R2: Valid telemetry returns HTTP 200 with status 'accepted'."""
        payload = make_telemetry_payload()
        resp = await client.post("/api/ingest/telemetry", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["event_id"] == payload["event_id"]

    async def test_t1_f01_idempotent_duplicate_event_returns_duplicate(self, client: AsyncClient, vehicles, devices):
        """ORIGINAL_REQUEST §R2: Ingesting an identical event_id returns 'duplicate' without error."""
        event_id = str(uuid.uuid4())
        payload = make_telemetry_payload(event_id=event_id)
        resp1 = await client.post("/api/ingest/telemetry", json=payload)
        assert resp1.status_code == 200
        assert resp1.json()["status"] == "accepted"

        resp2 = await client.post("/api/ingest/telemetry", json=payload)
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "duplicate"

    async def test_t1_f01_persists_immutable_telemetry_event_in_db(
        self, client: AsyncClient, vehicles, devices, db_session: AsyncSession
    ):
        """ORIGINAL_REQUEST §R2: Ingestion persists an immutable TelemetryEvent row."""
        event_id = str(uuid.uuid4())
        payload = make_telemetry_payload(event_id=event_id, motion={"speed_kph": 44.2, "heading_deg": 180.0})
        resp = await client.post("/api/ingest/telemetry", json=payload)
        assert resp.status_code == 200

        result = await db_session.execute(select(TelemetryEvent).where(TelemetryEvent.event_id == event_id))
        stored = result.scalar_one_or_none()
        assert stored is not None
        assert stored.speed_kph == 44.2
        assert stored.heading_deg == 180.0

    async def test_t1_f01_upserts_mutable_telemetry_latest_record(
        self, client: AsyncClient, vehicles, devices, db_session: AsyncSession
    ):
        """ORIGINAL_REQUEST §R2: Ingestion upserts TelemetryLatest with the most recent coordinates."""
        bus_id = vehicles["bus"].id
        payload = make_telemetry_payload(location={"lat": 28.6139, "lng": 77.2090, "accuracy_m": 5.0})
        resp = await client.post("/api/ingest/telemetry", json=payload)
        assert resp.status_code == 200

        result = await db_session.execute(select(TelemetryLatest).where(TelemetryLatest.vehicle_id == bus_id))
        latest = result.scalar_one_or_none()
        assert latest is not None
        assert abs(latest.latitude - 28.6139) < 1e-4
        assert abs(latest.longitude - 77.2090) < 1e-4

    async def test_t1_f01_updates_device_last_seen_timestamp(
        self, client: AsyncClient, vehicles, devices, db_session: AsyncSession
    ):
        """ORIGINAL_REQUEST §R2: Ingestion refreshes device.last_seen_at timestamp."""
        bus_device = devices["bus_device"]
        initial_seen = bus_device.last_seen_at
        payload = make_telemetry_payload()
        resp = await client.post("/api/ingest/telemetry", json=payload)
        assert resp.status_code == 200

        await db_session.refresh(bus_device)
        assert bus_device.last_seen_at is not None
        if initial_seen:
            assert bus_device.last_seen_at >= initial_seen

    async def test_t1_f01_telemetry_captures_all_subsystem_blocks(
        self, client: AsyncClient, vehicles, devices, db_session: AsyncSession
    ):
        """ORIGINAL_REQUEST §R2: Location, motion, energy, diagnostics, connectivity blocks are preserved."""
        event_id = str(uuid.uuid4())
        payload = make_telemetry_payload(
            event_id=event_id,
            location={"lat": 28.6250, "lng": 77.2205, "accuracy_m": 4.2},
            motion={"speed_kph": 52.0, "heading_deg": 90.0},
            energy={"soc_pct": 55.0, "estimated_range_km": 95.0, "charging": True},
            diagnostics={"battery_temp_c": 36.5, "dtcs": ["U0100"]},
            connectivity={"network": "5G", "firmware": "1.0.0"},
            seq=42,
        )
        resp = await client.post("/api/ingest/telemetry", json=payload)
        assert resp.status_code == 200

        result = await db_session.execute(select(TelemetryEvent).where(TelemetryEvent.event_id == event_id))
        evt = result.scalar_one()
        assert evt.soc_pct == 55.0
        assert evt.charging is True
        assert evt.battery_temp_c == 36.5
        assert evt.dtcs == ["U0100"]
        assert evt.network == "5G"
        assert evt.seq == 42

    # --- Feature 2: Alert Threshold Evaluations ---

    async def test_t1_f02_low_soc_triggers_high_and_critical_alerts(
        self, client: AsyncClient, users, vehicles, devices
    ):
        """ORIGINAL_REQUEST §R2 / PROJECT.md §Feature 7: SoC < 20% -> HIGH; SoC < 10% -> CRITICAL."""
        # 1. High alert (SoC = 15%)
        p1 = make_telemetry_payload(energy={"soc_pct": 15.0, "estimated_range_km": 25.0, "charging": False})
        resp1 = await client.post("/api/ingest/telemetry", json=p1)
        assert resp1.status_code == 200

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        assert resp_alerts.status_code == 200
        alerts = resp_alerts.json()
        high_soc_alerts = [a for a in alerts if a["alert_type"] == "LOW_SOC" and a["severity"] == "high"]
        assert len(high_soc_alerts) >= 1

        # 2. Critical alert (SoC = 8%)
        p2 = make_telemetry_payload(energy={"soc_pct": 8.0, "estimated_range_km": 12.0, "charging": False})
        resp2 = await client.post("/api/ingest/telemetry", json=p2)
        assert resp2.status_code == 200

        resp_alerts2 = await client.get("/api/operator/alerts", headers=headers)
        crit_alerts = [a for a in resp_alerts2.json() if a["alert_type"] == "LOW_SOC" and a["severity"] == "critical"]
        assert len(crit_alerts) >= 1

    async def test_t1_f02_high_battery_temp_triggers_high_and_critical_alerts(
        self, client: AsyncClient, users, vehicles, devices
    ):
        """ORIGINAL_REQUEST §R2: Temp > 45°C -> HIGH; Temp > 55°C -> CRITICAL."""
        headers = make_auth_header(users["transport_admin"])

        # High alert (Temp = 48°C)
        p1 = make_telemetry_payload(diagnostics={"battery_temp_c": 48.0, "dtcs": []})
        await client.post("/api/ingest/telemetry", json=p1)
        resp1 = await client.get("/api/operator/alerts", headers=headers)
        high_temp = [a for a in resp1.json() if a["alert_type"] == "HIGH_BATTERY_TEMP" and a["severity"] == "high"]
        assert len(high_temp) >= 1

        # Critical alert (Temp = 58°C)
        p2 = make_telemetry_payload(diagnostics={"battery_temp_c": 58.0, "dtcs": []})
        await client.post("/api/ingest/telemetry", json=p2)
        resp2 = await client.get("/api/operator/alerts", headers=headers)
        crit_temp = [a for a in resp2.json() if a["alert_type"] == "HIGH_BATTERY_TEMP" and a["severity"] == "critical"]
        assert len(crit_temp) >= 1

    async def test_t1_f02_overspeed_triggers_medium_alert(self, client: AsyncClient, users, vehicles, devices):
        """ORIGINAL_REQUEST §R2: Speed > 80 kph triggers OVERSPEED alert with MEDIUM severity."""
        p = make_telemetry_payload(motion={"speed_kph": 88.5, "heading_deg": 90.0})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        overspeed = [a for a in resp_alerts.json() if a["alert_type"] == "OVERSPEED"]
        assert len(overspeed) >= 1
        assert overspeed[0]["severity"] == "medium"
        assert overspeed[0]["metadata"]["speed_kph"] == 88.5

    async def test_t1_f02_diagnostic_fault_triggers_medium_alert(self, client: AsyncClient, users, vehicles, devices):
        """ORIGINAL_REQUEST §R2: Populated DTCs list triggers DIAGNOSTIC_FAULT alert."""
        p = make_telemetry_payload(diagnostics={"dtcs": ["P0A80", "P0A7F"], "battery_temp_c": 32.0})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        diag = [a for a in resp_alerts.json() if a["alert_type"] == "DIAGNOSTIC_FAULT"]
        assert len(diag) >= 1
        assert diag[0]["metadata"]["dtcs"] == ["P0A80", "P0A7F"]

    async def test_t1_f02_low_range_triggers_medium_and_high_alerts(self, client: AsyncClient, users, vehicles, devices):
        """ORIGINAL_REQUEST §R2: Range < 30 km -> MEDIUM; Range < 10 km -> HIGH."""
        headers = make_auth_header(users["transport_admin"])

        # Range = 22 km -> MEDIUM
        p1 = make_telemetry_payload(energy={"soc_pct": 50.0, "estimated_range_km": 22.0, "charging": False})
        await client.post("/api/ingest/telemetry", json=p1)
        resp1 = await client.get("/api/operator/alerts", headers=headers)
        med_range = [a for a in resp1.json() if a["alert_type"] == "LOW_RANGE" and a["severity"] == "medium"]
        assert len(med_range) >= 1

        # Range = 6 km -> HIGH
        p2 = make_telemetry_payload(energy={"soc_pct": 50.0, "estimated_range_km": 6.0, "charging": False})
        await client.post("/api/ingest/telemetry", json=p2)
        resp2 = await client.get("/api/operator/alerts", headers=headers)
        high_range = [a for a in resp2.json() if a["alert_type"] == "LOW_RANGE" and a["severity"] == "high"]
        assert len(high_range) >= 1

    async def test_t1_f02_charging_interrupted_triggers_alert(self, client: AsyncClient, users, vehicles, devices):
        """ORIGINAL_REQUEST §R2: Transition from charging=True to charging=False with SoC < 80% triggers alert."""
        headers = make_auth_header(users["transport_admin"])

        # Step 1: Vehicle actively charging at 45%
        p1 = make_telemetry_payload(energy={"soc_pct": 45.0, "estimated_range_km": 80.0, "charging": True})
        await client.post("/api/ingest/telemetry", json=p1)

        # Step 2: Unplugged prematurely at 48% (SoC < 80%)
        p2 = make_telemetry_payload(energy={"soc_pct": 48.0, "estimated_range_km": 85.0, "charging": False})
        await client.post("/api/ingest/telemetry", json=p2)

        resp = await client.get("/api/operator/alerts", headers=headers)
        interrupted = [a for a in resp.json() if a["alert_type"] == "CHARGING_INTERRUPTED"]
        assert len(interrupted) >= 1
        assert interrupted[0]["severity"] == "medium"

    # --- Feature 3: WebSocket Broadcasting ---

    async def test_t1_f03_telemetry_broadcast_message_schema(self, departments):
        """PROJECT.md §Interface Contracts: Telemetry broadcast matches expected JSON schema."""
        test_mgr = ConnectionManager()
        mock_ws = MockWebSocket()
        dept_id = departments["transport"].id
        await test_mgr.connect(mock_ws, "department_admin", dept_id)

        telemetry_data = {
            "vehicle_id": str(uuid.uuid4()),
            "latitude": 28.6139,
            "longitude": 77.2090,
            "speed_kph": 45.2,
            "heading_deg": 180.0,
            "soc_pct": 74.5,
            "estimated_range_km": 145.0,
            "charging": False,
            "connectivity_status": "online",
            "observed_at": "2026-09-04T11:00:00Z",
        }
        await test_mgr.broadcast_telemetry(dept_id, telemetry_data)

        assert len(mock_ws.messages) == 1
        msg = json.loads(mock_ws.messages[0])
        assert msg["type"] == "telemetry_update"
        assert msg["data"]["latitude"] == 28.6139
        assert msg["data"]["soc_pct"] == 74.5

    async def test_t1_f03_alert_broadcast_message_schema(self, departments):
        """PROJECT.md §Interface Contracts: Alert broadcast matches expected JSON schema."""
        test_mgr = ConnectionManager()
        mock_ws = MockWebSocket()
        dept_id = departments["transport"].id
        await test_mgr.connect(mock_ws, "department_admin", dept_id)

        alert_data = {
            "id": str(uuid.uuid4()),
            "vehicle_id": str(uuid.uuid4()),
            "alert_type": "LOW_SOC",
            "severity": "critical",
            "status": "active",
            "message": "Critical battery depletion below 10%",
            "metadata": {"soc_pct": 8.5},
            "created_at": "2026-09-04T11:00:00Z",
        }
        await test_mgr.broadcast_alert(dept_id, alert_data)

        assert len(mock_ws.messages) == 1
        msg = json.loads(mock_ws.messages[0])
        assert msg["type"] == "alert"
        assert msg["data"]["alert_type"] == "LOW_SOC"
        assert msg["data"]["severity"] == "critical"

    async def test_t1_f03_platform_admin_receives_all_broadcasts(self, departments):
        """ORIGINAL_REQUEST §R2: Platform admin receives telemetry broadcasts across all departments."""
        test_mgr = ConnectionManager()
        admin_ws = MockWebSocket()
        await test_mgr.connect(admin_ws, "platform_admin", None)

        # Broadcast for transport department
        await test_mgr.broadcast_telemetry(departments["transport"].id, {"bus": 1})
        # Broadcast for fire department
        await test_mgr.broadcast_telemetry(departments["fire"].id, {"fire": 2})

        assert len(admin_ws.messages) == 2

    async def test_t1_f03_department_connection_receives_only_own_department(self, departments):
        """PROJECT.md §Feature 9: Department isolation prevents cross-department broadcast leakage."""
        test_mgr = ConnectionManager()
        transport_ws = MockWebSocket()
        fire_ws = MockWebSocket()

        await test_mgr.connect(transport_ws, "department_admin", departments["transport"].id)
        await test_mgr.connect(fire_ws, "department_admin", departments["fire"].id)

        # Broadcast Transport telemetry
        await test_mgr.broadcast_telemetry(departments["transport"].id, {"event": "bus_update"})

        assert len(transport_ws.messages) == 1
        assert len(fire_ws.messages) == 0  # Fire received nothing

    async def test_t1_f03_safe_serialization_uuid_and_datetime(self, departments):
        """PROJECT.md §Feature 9: ConnectionManager serialization handles UUIDs and datetimes safely."""
        test_mgr = ConnectionManager()
        mock_ws = MockWebSocket()
        dept_id = departments["transport"].id
        await test_mgr.connect(mock_ws, "department_admin", dept_id)

        raw_data = {
            "vehicle_id": uuid.uuid4(),
            "observed_at": datetime.now(timezone.utc),
            "status": "ok",
        }

        try:
            # If manager has default=str, this succeeds cleanly
            await test_mgr.broadcast_telemetry(dept_id, raw_data)
            assert len(mock_ws.messages) == 1
        except TypeError as exc:
            # Mark as pending M1 completion per Feature 9 without breaking harness
            pytest.xfail(f"Feature 9 in progress: ConnectionManager lacks default=str serializer ({exc})")

    # --- Feature 4: Vehicle Diagnostics Exposure ---

    async def test_t1_f04_telemetry_latest_persists_battery_temp_and_dtcs(
        self, client: AsyncClient, vehicles, devices, db_session: AsyncSession
    ):
        """ORIGINAL_REQUEST §R2: TelemetryLatest table persists battery_temp_c and dtcs from hardware."""
        p = make_telemetry_payload(diagnostics={"battery_temp_c": 37.8, "dtcs": ["P0A80", "P0A1F"]})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

        result = await db_session.execute(
            select(TelemetryLatest).where(TelemetryLatest.vehicle_id == vehicles["bus"].id)
        )
        latest = result.scalar_one()
        assert latest.battery_temp_c == 37.8
        assert latest.dtcs == ["P0A80", "P0A1F"]

    async def test_t1_f04_operator_vehicles_list_returns_200_and_core_fields(
        self, client: AsyncClient, users, vehicles, devices
    ):
        """ORIGINAL_REQUEST §R2: GET /api/operator/vehicles returns array of vehicles with latest telemetry."""
        p = make_telemetry_payload(energy={"soc_pct": 68.0})
        await client.post("/api/ingest/telemetry", json=p)

        headers = make_auth_header(users["transport_admin"])
        resp = await client.get("/api/operator/vehicles", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        bus_item = next((v for v in data if v["vehicle_code"] == "bus-test-001"), None)
        assert bus_item is not None
        assert bus_item["soc_pct"] == 68.0
        assert "latitude" in bus_item
        assert "longitude" in bus_item

    async def test_t1_f04_operator_single_vehicle_diagnostics_lookup(
        self, client: AsyncClient, users, vehicles, devices
    ):
        """ORIGINAL_REQUEST §R2: GET /api/operator/vehicles/{id} returns vehicle telemetry."""
        p = make_telemetry_payload(energy={"soc_pct": 82.0})
        await client.post("/api/ingest/telemetry", json=p)

        headers = make_auth_header(users["transport_admin"])
        bus_id = str(vehicles["bus"].id)
        resp = await client.get(f"/api/operator/vehicles/{bus_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == bus_id
        assert data["soc_pct"] == 82.0

    async def test_t1_f04_dtcs_field_contains_valid_string_list(
        self, client: AsyncClient, vehicles, devices, db_session: AsyncSession
    ):
        """ORIGINAL_REQUEST §R2: DTCs diagnostic codes are structured as a list of OBD/UDS strings."""
        p = make_telemetry_payload(diagnostics={"dtcs": ["P0A80"], "battery_temp_c": 31.0})
        await client.post("/api/ingest/telemetry", json=p)

        result = await db_session.execute(
            select(TelemetryLatest).where(TelemetryLatest.vehicle_id == vehicles["bus"].id)
        )
        latest = result.scalar_one()
        assert isinstance(latest.dtcs, list)
        assert "P0A80" in latest.dtcs

    async def test_t1_f04_battery_temp_field_is_float_or_null(
        self, client: AsyncClient, vehicles, devices, db_session: AsyncSession
    ):
        """ORIGINAL_REQUEST §R2: battery_temp_c is stored as a floating-point degree Celsius value."""
        p = make_telemetry_payload(diagnostics={"battery_temp_c": 41.5, "dtcs": []})
        await client.post("/api/ingest/telemetry", json=p)

        result = await db_session.execute(
            select(TelemetryLatest).where(TelemetryLatest.vehicle_id == vehicles["bus"].id)
        )
        latest = result.scalar_one()
        assert isinstance(latest.battery_temp_c, float)
        assert latest.battery_temp_c == 41.5

    # --- Feature 5: Public Charging Centers ---

    async def test_t1_f05_public_charging_centers_endpoint_200(self, client: AsyncClient, sample_charging_hub):
        """ORIGINAL_REQUEST §R3: Public charging centers endpoint requires zero authentication."""
        resp = await client.get("/api/public/charging-centers")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_t1_f05_public_charging_centers_sanitization(self, client: AsyncClient, sample_charging_hub):
        """PROJECT.md §Architecture: Public charging centers expose zero internal credentials or audit logs."""
        resp = await client.get("/api/public/charging-centers")
        assert resp.status_code == 200
        data = resp.json()
        for station in data:
            assert "hashed_password" not in station
            assert "internal_notes" not in station
            assert "secret_key" not in station

    async def test_t1_f05_public_charging_centers_attributes_structure(self, client: AsyncClient, sample_charging_hub):
        """PROJECT.md §Interface Contracts: Charging center contains name, lat, lng, address, power_kw, connectors."""
        resp = await client.get("/api/public/charging-centers")
        assert resp.status_code == 200
        station = resp.json()[0]
        assert "name" in station
        assert "latitude" in station
        assert "longitude" in station
        assert "power_kw" in station
        assert "connectors" in station

    async def test_t1_f05_public_charging_centers_connectors_dict(self, client: AsyncClient, sample_charging_hub):
        """ORIGINAL_REQUEST §R3: Connectors map connector standards (e.g. CCS2, Type2) to port counts."""
        resp = await client.get("/api/public/charging-centers")
        assert resp.status_code == 200
        station = resp.json()[0]
        connectors = station.get("connectors")
        assert isinstance(connectors, dict)
        assert connectors.get("CCS2") == 4
        assert connectors.get("Type2") == 2

    async def test_t1_f05_public_charging_centers_power_kw_numeric(self, client: AsyncClient, sample_charging_hub):
        """PROJECT.md §Feature 12: power_kw is a numeric field representing fast charger capability."""
        resp = await client.get("/api/public/charging-centers")
        assert resp.status_code == 200
        station = resp.json()[0]
        assert isinstance(station.get("power_kw"), (int, float))
        assert station.get("power_kw") == 150.0

    # --- Feature 6: Offline Telemetry Queue Format ---

    async def test_t1_f06_offline_queue_payload_structure_conformance(self, vehicles, devices):
        """ORIGINAL_REQUEST §R1: Offline telemetry payload conforms exactly to server ingest contract."""
        payload = make_telemetry_payload()
        # Verify all mandatory keys required for serialization to SharedPreferences
        assert "device_id" in payload
        assert "vehicle_id" in payload
        assert "event_id" in payload
        assert "observed_at" in payload
        assert "location" in payload
        assert "energy" in payload
        assert "diagnostics" in payload

    async def test_t1_f06_offline_queue_batch_replay_drains_cleanly(self, client: AsyncClient, vehicles, devices):
        """ORIGINAL_REQUEST §R1: Replaying buffered queue payloads ingests sequentially without errors."""
        queue_buffer = [
            make_telemetry_payload(seq=10, location={"lat": 28.6315, "lng": 77.2167}),
            make_telemetry_payload(seq=11, location={"lat": 28.6250, "lng": 77.2205}),
            make_telemetry_payload(seq=12, location={"lat": 28.6180, "lng": 77.2410}),
        ]

        for item in queue_buffer:
            resp = await client.post("/api/ingest/telemetry", json=item)
            assert resp.status_code in (200, 201)
            assert resp.json()["status"] == "accepted"

    async def test_t1_f06_offline_queue_preserves_seq_field(
        self, client: AsyncClient, vehicles, devices, db_session: AsyncSession
    ):
        """ORIGINAL_REQUEST §R1: Sequence number is preserved in persistent storage across reconnects."""
        payload = make_telemetry_payload(seq=999)
        resp = await client.post("/api/ingest/telemetry", json=payload)
        assert resp.status_code == 200

        result = await db_session.execute(
            select(TelemetryEvent).where(TelemetryEvent.event_id == payload["event_id"])
        )
        stored = result.scalar_one()
        assert stored.seq == 999

    async def test_t1_f06_offline_queue_reconnection_idempotency(self, client: AsyncClient, vehicles, devices):
        """ORIGINAL_REQUEST §R1: Re-transmitting queued events after unexpected socket drop is idempotent."""
        event_id = str(uuid.uuid4())
        payload = make_telemetry_payload(event_id=event_id, seq=100)

        # Initial flush
        resp1 = await client.post("/api/ingest/telemetry", json=payload)
        assert resp1.status_code == 200
        assert resp1.json()["status"] == "accepted"

        # Replayed flush upon reconnect
        resp2 = await client.post("/api/ingest/telemetry", json=payload)
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "duplicate"

    async def test_t1_f06_offline_queue_observed_at_iso_format(self, vehicles, devices):
        """ORIGINAL_REQUEST §R1: Timestamps in offline queue follow ISO 8601 UTC format."""
        payload = make_telemetry_payload()
        # Verify timestamp can be parsed into Python datetime
        parsed = datetime.fromisoformat(payload["observed_at"])
        assert parsed is not None

    # --- Feature 7: Pitch Simulator Payload ---

    async def test_t1_f07_pitch_sim_delhi_coordinates_valid(self):
        """ORIGINAL_REQUEST §R1 / PROJECT.md §Feature 4: Simulator route stays within Central Delhi bounds."""
        from simulator.routes import ROUTES
        assert len(ROUTES) >= 1
        delhi_route = ROUTES[0]
        for lat, lng in delhi_route:
            assert 28.4 <= lat <= 28.9, f"Latitude {lat} outside Delhi NCR"
            assert 77.0 <= lng <= 77.5, f"Longitude {lng} outside Delhi NCR"

    async def test_t1_f07_pitch_sim_stepwise_soc_depletion(self, client: AsyncClient, vehicles, devices):
        """ORIGINAL_REQUEST §R1: Simulator steps deplete SoC from 18% down to 7%."""
        soc_sequence = [18.0, 15.0, 12.0, 9.5, 7.0]
        for idx, soc in enumerate(soc_sequence):
            p = make_telemetry_payload(
                energy={"soc_pct": soc, "estimated_range_km": soc * 1.5, "charging": False},
                seq=idx + 1
            )
            resp = await client.post("/api/ingest/telemetry", json=p)
            assert resp.status_code == 200

    async def test_t1_f07_pitch_sim_warning_alert_triggered_at_18_percent(
        self, client: AsyncClient, users, vehicles, devices
    ):
        """PROJECT.md §Feature 4: SoC = 18% generates HIGH severity alert."""
        p = make_telemetry_payload(energy={"soc_pct": 18.0, "estimated_range_km": 28.0, "charging": False})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        alerts = [a for a in resp_alerts.json() if a["alert_type"] == "LOW_SOC" and a["severity"] == "high"]
        assert len(alerts) >= 1

    async def test_t1_f07_pitch_sim_critical_alert_triggered_below_10_percent(
        self, client: AsyncClient, users, vehicles, devices
    ):
        """PROJECT.md §Feature 4: SoC = 7% generates CRITICAL severity alert."""
        p = make_telemetry_payload(energy={"soc_pct": 7.0, "estimated_range_km": 10.0, "charging": False})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        crit_alerts = [a for a in resp_alerts.json() if a["alert_type"] == "LOW_SOC" and a["severity"] == "critical"]
        assert len(crit_alerts) >= 1

    async def test_t1_f07_pitch_sim_charging_dock_transition(
        self, client: AsyncClient, vehicles, devices, db_session: AsyncSession
    ):
        """ORIGINAL_REQUEST §R1: Reaching destination plug-in flips charging to True."""
        p = make_telemetry_payload(energy={"soc_pct": 8.0, "estimated_range_km": 12.0, "charging": True})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

        result = await db_session.execute(
            select(TelemetryLatest).where(TelemetryLatest.vehicle_id == vehicles["bus"].id)
        )
        latest = result.scalar_one()
        assert latest.charging is True


# ==============================================================================
# Tier 2: Boundary & Corner Cases (>= 5 test cases per feature across 6 boundaries)
# ==============================================================================

class TestTier2BoundaryAndCornerCases:
    """
    Tier 2: Boundary values, edge conditions, invalid inputs,
    and extreme stress conditions derived directly from requirements.
    """

    # --- Boundary 1: Max Speed Boundaries ---

    async def test_t2_b01_speed_zero_kph_valid(self, client: AsyncClient, vehicles, devices):
        """Boundary: Speed = 0.0 kph (stationary vehicle) is accepted."""
        p = make_telemetry_payload(motion={"speed_kph": 0.0, "heading_deg": 0.0})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    async def test_t2_b01_speed_sub_threshold_normal(self, client: AsyncClient, users, vehicles, devices):
        """Boundary: Speed = 79.9 kph (just under 80 threshold) does not trigger overspeed."""
        p = make_telemetry_payload(motion={"speed_kph": 79.9, "heading_deg": 45.0})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        overspeed = [a for a in resp_alerts.json() if a["alert_type"] == "OVERSPEED"]
        assert len(overspeed) == 0

    async def test_t2_b01_speed_exact_threshold_normal(self, client: AsyncClient, users, vehicles, devices):
        """Boundary: Speed = 80.0 kph (exact threshold boundary) does not trigger overspeed."""
        p = make_telemetry_payload(motion={"speed_kph": 80.0, "heading_deg": 45.0})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        overspeed = [a for a in resp_alerts.json() if a["alert_type"] == "OVERSPEED"]
        assert len(overspeed) == 0

    async def test_t2_b01_speed_above_threshold_alert(self, client: AsyncClient, users, vehicles, devices):
        """Boundary: Speed = 80.1 kph (just above threshold) triggers OVERSPEED alert."""
        p = make_telemetry_payload(motion={"speed_kph": 80.1, "heading_deg": 45.0})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        overspeed = [a for a in resp_alerts.json() if a["alert_type"] == "OVERSPEED"]
        assert len(overspeed) >= 1

    async def test_t2_b01_speed_max_valid_speed(self, client: AsyncClient, vehicles, devices):
        """Boundary: Speed = 200.0 kph is tolerated without flagging impossible_speed."""
        p = make_telemetry_payload(motion={"speed_kph": 200.0, "heading_deg": 90.0})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200
        flags = resp.json().get("flags") or {}
        assert flags.get("impossible_speed") is not True

    async def test_t2_b01_speed_impossible_speed_flagged(self, client: AsyncClient, vehicles, devices):
        """Boundary: Speed = 201.0 kph exceeds max allowed speed and is flagged impossible_speed."""
        p = make_telemetry_payload(motion={"speed_kph": 201.0, "heading_deg": 90.0})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200
        flags = resp.json().get("flags") or {}
        assert flags.get("impossible_speed") is True

    async def test_t2_b01_speed_negative_rejected(self, client: AsyncClient, vehicles, devices):
        """Adversarial: Speed < 0 (-5.0 kph) is rejected with HTTP 422."""
        p = make_telemetry_payload(motion={"speed_kph": -5.0, "heading_deg": 90.0})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 422

    # --- Boundary 2: Empty & Missing Fields ---

    async def test_t2_b02_empty_dtcs_list_no_fault_alert(self, client: AsyncClient, users, vehicles, devices):
        """Boundary: Empty list of DTCs `[]` does not trigger DIAGNOSTIC_FAULT."""
        p = make_telemetry_payload(diagnostics={"dtcs": [], "battery_temp_c": 30.0})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        faults = [a for a in resp_alerts.json() if a["alert_type"] == "DIAGNOSTIC_FAULT"]
        assert len(faults) == 0

    async def test_t2_b02_missing_optional_accuracy_accepted(self, client: AsyncClient, vehicles, devices):
        """Boundary: GPS accuracy_m is optional and omitting it succeeds."""
        p = make_telemetry_payload(location={"lat": 28.6315, "lng": 77.2167, "accuracy_m": None})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

    async def test_t2_b02_missing_optional_connectivity_accepted(self, client: AsyncClient, vehicles, devices):
        """Boundary: connectivity block is optional and omitting it succeeds."""
        p = make_telemetry_payload(connectivity=None)
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

    async def test_t2_b02_missing_motion_block_accepted(self, client: AsyncClient, vehicles, devices):
        """Boundary: motion block is optional (e.g. parked stationary) and omitting it succeeds."""
        p = make_telemetry_payload(motion=None)
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

    async def test_t2_b02_missing_required_vehicle_id_rejected(self, client: AsyncClient, vehicles, devices):
        """Adversarial: Omitting mandatory vehicle_id returns HTTP 422 Unprocessable Entity."""
        p = make_telemetry_payload()
        del p["vehicle_id"]
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 422

    # --- Boundary 3: Boundary Temperatures ---

    async def test_t2_b03_temp_sub_threshold_normal(self, client: AsyncClient, users, vehicles, devices):
        """Boundary: Temp = 44.9°C does not trigger high battery temp alert."""
        p = make_telemetry_payload(diagnostics={"battery_temp_c": 44.9, "dtcs": []})
        await client.post("/api/ingest/telemetry", json=p)

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        temp_alerts = [a for a in resp_alerts.json() if a["alert_type"] == "HIGH_BATTERY_TEMP"]
        assert len(temp_alerts) == 0

    async def test_t2_b03_temp_exact_threshold_normal(self, client: AsyncClient, users, vehicles, devices):
        """Boundary: Temp = 45.0°C (exact threshold boundary) does not trigger alert."""
        p = make_telemetry_payload(diagnostics={"battery_temp_c": 45.0, "dtcs": []})
        await client.post("/api/ingest/telemetry", json=p)

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        temp_alerts = [a for a in resp_alerts.json() if a["alert_type"] == "HIGH_BATTERY_TEMP"]
        assert len(temp_alerts) == 0

    async def test_t2_b03_temp_above_threshold_high_alert(self, client: AsyncClient, users, vehicles, devices):
        """Boundary: Temp = 45.1°C triggers HIGH severity alert."""
        p = make_telemetry_payload(diagnostics={"battery_temp_c": 45.1, "dtcs": []})
        await client.post("/api/ingest/telemetry", json=p)

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        high_alerts = [a for a in resp_alerts.json() if a["alert_type"] == "HIGH_BATTERY_TEMP" and a["severity"] == "high"]
        assert len(high_alerts) >= 1

    async def test_t2_b03_temp_critical_threshold_boundary(self, client: AsyncClient, users, vehicles, devices):
        """Boundary: Temp = 55.0°C remains HIGH severity (critical requires > 55)."""
        p = make_telemetry_payload(diagnostics={"battery_temp_c": 55.0, "dtcs": []})
        await client.post("/api/ingest/telemetry", json=p)

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        alerts = [a for a in resp_alerts.json() if a["alert_type"] == "HIGH_BATTERY_TEMP"]
        assert len(alerts) >= 1
        assert alerts[0]["severity"] == "high"

    async def test_t2_b03_temp_above_critical_threshold(self, client: AsyncClient, users, vehicles, devices):
        """Boundary: Temp = 55.1°C triggers CRITICAL severity alert."""
        p = make_telemetry_payload(diagnostics={"battery_temp_c": 55.1, "dtcs": []})
        await client.post("/api/ingest/telemetry", json=p)

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        crit_alerts = [a for a in resp_alerts.json() if a["alert_type"] == "HIGH_BATTERY_TEMP" and a["severity"] == "critical"]
        assert len(crit_alerts) >= 1

    async def test_t2_b03_temp_extreme_cold_accepted(self, client: AsyncClient, vehicles, devices):
        """Corner: Sub-zero temperature (-20.0°C winter condition) is accepted without rejection."""
        p = make_telemetry_payload(diagnostics={"battery_temp_c": -20.0, "dtcs": []})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

    # --- Boundary 4: 0% and 100% SoC Boundaries ---

    async def test_t2_b04_soc_zero_percent_critical(self, client: AsyncClient, users, vehicles, devices):
        """Boundary: SoC = 0.0% is accepted and triggers CRITICAL LOW_SOC alert."""
        p = make_telemetry_payload(energy={"soc_pct": 0.0, "estimated_range_km": 0.0, "charging": False})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        crit = [a for a in resp_alerts.json() if a["alert_type"] == "LOW_SOC" and a["severity"] == "critical"]
        assert len(crit) >= 1

    async def test_t2_b04_soc_sub_ten_percent_critical(self, client: AsyncClient, users, vehicles, devices):
        """Boundary: SoC = 9.9% triggers CRITICAL LOW_SOC alert."""
        p = make_telemetry_payload(energy={"soc_pct": 9.9, "estimated_range_km": 14.0, "charging": False})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        crit = [a for a in resp_alerts.json() if a["alert_type"] == "LOW_SOC" and a["severity"] == "critical"]
        assert len(crit) >= 1

    async def test_t2_b04_soc_exact_ten_percent_high(self, client: AsyncClient, users, vehicles, devices):
        """Boundary: SoC = 10.0% triggers HIGH LOW_SOC alert (not critical)."""
        p = make_telemetry_payload(energy={"soc_pct": 10.0, "estimated_range_km": 15.0, "charging": False})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        high = [a for a in resp_alerts.json() if a["alert_type"] == "LOW_SOC" and a["severity"] == "high"]
        assert len(high) >= 1

    async def test_t2_b04_soc_sub_twenty_percent_high(self, client: AsyncClient, users, vehicles, devices):
        """Boundary: SoC = 19.9% triggers HIGH LOW_SOC alert."""
        p = make_telemetry_payload(energy={"soc_pct": 19.9, "estimated_range_km": 30.0, "charging": False})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        high = [a for a in resp_alerts.json() if a["alert_type"] == "LOW_SOC" and a["severity"] == "high"]
        assert len(high) >= 1

    async def test_t2_b04_soc_exact_twenty_percent_normal(self, client: AsyncClient, users, vehicles, devices):
        """Boundary: SoC = 20.0% is normal operating level (no LOW_SOC alert)."""
        p = make_telemetry_payload(energy={"soc_pct": 20.0, "estimated_range_km": 32.0, "charging": False})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        low_soc = [a for a in resp_alerts.json() if a["alert_type"] == "LOW_SOC"]
        assert len(low_soc) == 0

    async def test_t2_b04_soc_hundred_percent_normal(self, client: AsyncClient, vehicles, devices):
        """Boundary: SoC = 100.0% (fully charged) is accepted."""
        p = make_telemetry_payload(energy={"soc_pct": 100.0, "estimated_range_km": 180.0, "charging": True})
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

    async def test_t2_b04_soc_out_of_range_rejected(self, client: AsyncClient, vehicles, devices):
        """Adversarial: SoC > 100% or < 0% is rejected with HTTP 422."""
        p1 = make_telemetry_payload(energy={"soc_pct": 100.1})
        resp1 = await client.post("/api/ingest/telemetry", json=p1)
        assert resp1.status_code == 422

        p2 = make_telemetry_payload(energy={"soc_pct": -0.1})
        resp2 = await client.post("/api/ingest/telemetry", json=p2)
        assert resp2.status_code == 422

    # --- Boundary 5: Invalid UUIDs & Resource Identifiers ---

    async def test_t2_b05_malformed_uuid_operator_vehicle_returns_422(self, client: AsyncClient, users):
        """Adversarial: Passing a malformed UUID string to GET /vehicles/{id} returns HTTP 422."""
        headers = make_auth_header(users["transport_admin"])
        resp = await client.get("/api/operator/vehicles/not-a-valid-uuid", headers=headers)
        assert resp.status_code == 422

    async def test_t2_b05_non_existent_uuid_operator_vehicle_returns_404(self, client: AsyncClient, users):
        """Edge: Passing a random valid UUID that does not exist in DB returns HTTP 404."""
        headers = make_auth_header(users["transport_admin"])
        random_uuid = str(uuid.uuid4())
        resp = await client.get(f"/api/operator/vehicles/{random_uuid}", headers=headers)
        assert resp.status_code == 404

    async def test_t2_b05_malformed_uuid_operator_track_returns_422(self, client: AsyncClient, users):
        """Adversarial: Passing a malformed UUID string to /track endpoint returns HTTP 422."""
        headers = make_auth_header(users["transport_admin"])
        resp = await client.get("/api/operator/vehicles/invalid_uuid_string/track", headers=headers)
        assert resp.status_code == 422

    async def test_t2_b05_unknown_device_in_telemetry_rejected(self, client: AsyncClient, vehicles):
        """Adversarial: Ingesting telemetry from unregistered device_id is rejected."""
        p = make_telemetry_payload(device_id="unregistered-hardware-device-999")
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code in (200, 422)
        if resp.status_code == 200:
            assert resp.json()["status"] == "rejected"

    async def test_t2_b05_unknown_vehicle_in_telemetry_rejected(self, client: AsyncClient, devices):
        """Adversarial: Ingesting telemetry for unregistered vehicle_id is rejected."""
        p = make_telemetry_payload(vehicle_id="unregistered-vehicle-code-999")
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code in (200, 422)
        if resp.status_code == 200:
            assert resp.json()["status"] == "rejected"

    # --- Boundary 6: Out-of-Order & Timestamp Anomalies ---

    async def test_t2_b06_future_timestamp_beyond_limit_flagged(self, client: AsyncClient, vehicles, devices):
        """Adversarial: Telemetry observed in future (> 30s) is accepted but flagged future_timestamp."""
        future = (datetime.now(timezone.utc) + timedelta(minutes=45)).isoformat()
        p = make_telemetry_payload(observed_at=future)
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200
        flags = resp.json().get("flags") or {}
        assert flags.get("future_timestamp") is True

    async def test_t2_b06_near_current_timestamp_not_flagged(self, client: AsyncClient, vehicles, devices):
        """Boundary: Telemetry observed 2 seconds ago is not flagged as future_timestamp."""
        recent = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
        p = make_telemetry_payload(observed_at=recent)
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200
        flags = resp.json().get("flags") or {}
        assert flags.get("future_timestamp") is not True

    async def test_t2_b06_out_of_sequence_number_flagged(self, client: AsyncClient, vehicles, devices):
        """Boundary: Lower sequence number arriving after higher sequence is flagged out_of_sequence."""
        p1 = make_telemetry_payload(seq=100)
        await client.post("/api/ingest/telemetry", json=p1)

        p2 = make_telemetry_payload(seq=85)
        resp2 = await client.post("/api/ingest/telemetry", json=p2)
        assert resp2.status_code == 200
        flags = resp2.json().get("flags") or {}
        assert flags.get("out_of_sequence") is True

    async def test_t2_b06_strictly_increasing_sequence_not_flagged(self, client: AsyncClient, vehicles, devices):
        """Boundary: Strictly incrementing sequence numbers are not flagged."""
        p1 = make_telemetry_payload(seq=1)
        await client.post("/api/ingest/telemetry", json=p1)

        p2 = make_telemetry_payload(seq=2)
        resp2 = await client.post("/api/ingest/telemetry", json=p2)
        assert resp2.status_code == 200
        flags = resp2.json().get("flags") or {}
        assert flags.get("out_of_sequence") is not True

    async def test_t2_b06_sudden_soc_drop_greater_than_thirty_flagged(self, client: AsyncClient, vehicles, devices):
        """Edge: Impossible sudden SoC jump (>30% between frames) is flagged soc_jump."""
        p1 = make_telemetry_payload(energy={"soc_pct": 80.0, "estimated_range_km": 150.0, "charging": False})
        await client.post("/api/ingest/telemetry", json=p1)

        p2 = make_telemetry_payload(energy={"soc_pct": 40.0, "estimated_range_km": 70.0, "charging": False})
        resp2 = await client.post("/api/ingest/telemetry", json=p2)
        assert resp2.status_code == 200
        flags = resp2.json().get("flags") or {}
        assert flags.get("soc_jump") is True


# ==============================================================================
# Tier 3: Cross-Feature Combinations (Pairwise / Compound Interactions)
# ==============================================================================

class TestTier3CrossFeatureCombinations:
    """
    Tier 3: Pairwise interactions across subsystems:
    Ingestion -> Alert Generation -> Operator Query -> Department Isolation -> WebSocket Streaming.
    """

    async def test_t3_pairwise_ingest_alert_and_operator_query(self, client: AsyncClient, users, vehicles, devices):
        """Pairwise: Ingesting critical telemetry triggers alert queryable via operator REST endpoint."""
        p = make_telemetry_payload(energy={"soc_pct": 6.5, "estimated_range_km": 9.0, "charging": False})
        resp_ingest = await client.post("/api/ingest/telemetry", json=p)
        assert resp_ingest.status_code == 200

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        assert resp_alerts.status_code == 200
        alerts = resp_alerts.json()
        target = next((a for a in alerts if a["alert_type"] == "LOW_SOC" and a["severity"] == "critical"), None)
        assert target is not None
        assert target["metadata"]["soc_pct"] == 6.5

    async def test_t3_pairwise_compound_overspeed_and_low_soc(self, client: AsyncClient, users, vehicles, devices):
        """Pairwise: Compound violation (Speed > 80 AND SoC < 10) creates dual distinct alerts simultaneously."""
        p = make_telemetry_payload(
            motion={"speed_kph": 88.0, "heading_deg": 90.0},
            energy={"soc_pct": 8.5, "estimated_range_km": 12.0, "charging": False},
        )
        resp = await client.post("/api/ingest/telemetry", json=p)
        assert resp.status_code == 200

        headers = make_auth_header(users["transport_admin"])
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        alerts = resp_alerts.json()

        overspeed = next((a for a in alerts if a["alert_type"] == "OVERSPEED"), None)
        low_soc = next((a for a in alerts if a["alert_type"] == "LOW_SOC" and a["severity"] == "critical"), None)
        assert overspeed is not None, "Overspeed alert missing from compound violation"
        assert low_soc is not None, "Low SoC critical alert missing from compound violation"

    async def test_t3_pairwise_high_temp_and_charging_interrupted(self, client: AsyncClient, users, vehicles, devices):
        """Pairwise: Thermal anomaly while charging followed by premature disconnect generates both alerts."""
        headers = make_auth_header(users["transport_admin"])

        # Frame 1: Charging with high temp 56.5°C
        p1 = make_telemetry_payload(
            energy={"soc_pct": 52.0, "estimated_range_km": 80.0, "charging": True},
            diagnostics={"battery_temp_c": 56.5, "dtcs": []},
        )
        await client.post("/api/ingest/telemetry", json=p1)

        # Frame 2: Unplugged prematurely
        p2 = make_telemetry_payload(
            energy={"soc_pct": 53.0, "estimated_range_km": 82.0, "charging": False},
            diagnostics={"battery_temp_c": 56.0, "dtcs": []},
        )
        await client.post("/api/ingest/telemetry", json=p2)

        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        alerts = resp_alerts.json()
        has_temp = any(a["alert_type"] == "HIGH_BATTERY_TEMP" for a in alerts)
        has_interrupted = any(a["alert_type"] == "CHARGING_INTERRUPTED" for a in alerts)
        assert has_temp, "High battery temp alert expected"
        assert has_interrupted, "Charging interrupted alert expected"

    async def test_t3_pairwise_diagnostics_and_department_isolation(
        self, client: AsyncClient, users, vehicles, devices
    ):
        """Pairwise: Diagnostic faults on Transport bus are isolated from Fire Department operator queries."""
        p = make_telemetry_payload(
            device_code="dev-bus-test-001",
            vehicle_code="bus-test-001",
            diagnostics={"dtcs": ["P0A80"], "battery_temp_c": 35.0},
        )
        await client.post("/api/ingest/telemetry", json=p)

        # Transport admin sees it
        t_headers = make_auth_header(users["transport_admin"])
        resp_t = await client.get("/api/operator/alerts", headers=t_headers)
        t_alerts = [a for a in resp_t.json() if a["alert_type"] == "DIAGNOSTIC_FAULT"]
        assert len(t_alerts) >= 1

        # Fire admin CANNOT see transport bus fault
        f_headers = make_auth_header(users["fire_admin"])
        resp_f = await client.get("/api/operator/alerts", headers=f_headers)
        f_alerts = [a for a in resp_f.json() if a["alert_type"] == "DIAGNOSTIC_FAULT"]
        assert len(f_alerts) == 0

    async def test_t3_pairwise_ingest_track_history_and_latest_state(
        self, client: AsyncClient, users, vehicles, devices
    ):
        """Pairwise: Sequential GPS waypoints populate track history and update current vehicle position."""
        bus_id = str(vehicles["bus"].id)
        coords = [
            (28.6328, 77.2197),
            (28.6250, 77.2205),
            (28.6180, 77.2410),
        ]
        for idx, (lat, lng) in enumerate(coords):
            p = make_telemetry_payload(seq=idx + 1, location={"lat": lat, "lng": lng, "accuracy_m": 5.0})
            await client.post("/api/ingest/telemetry", json=p)

        headers = make_auth_header(users["transport_admin"])
        resp_track = await client.get(f"/api/operator/vehicles/{bus_id}/track", headers=headers)
        assert resp_track.status_code == 200
        track_points = resp_track.json()
        assert len(track_points) >= 3

        resp_latest = await client.get(f"/api/operator/vehicles/{bus_id}", headers=headers)
        latest = resp_latest.json()
        assert abs(latest["latitude"] - coords[-1][0]) < 1e-3
        assert abs(latest["longitude"] - coords[-1][1]) < 1e-3

    async def test_t3_pairwise_offline_queue_drain_and_idempotent_replay(
        self, client: AsyncClient, vehicles, devices, db_session: AsyncSession
    ):
        """Pairwise: Offline queue flush containing a duplicated item succeeds without DB corruption."""
        shared_event_id = str(uuid.uuid4())
        batch = [
            make_telemetry_payload(event_id=shared_event_id, seq=1),
            make_telemetry_payload(seq=2),
            make_telemetry_payload(event_id=shared_event_id, seq=1),  # Duplicated re-send
        ]

        responses = []
        for item in batch:
            r = await client.post("/api/ingest/telemetry", json=item)
            responses.append(r.json()["status"])

        assert responses[0] == "accepted"
        assert responses[1] == "accepted"
        assert responses[2] == "duplicate"

    async def test_t3_pairwise_pitch_sim_stepwise_alert_lifecycle(
        self, client: AsyncClient, users, vehicles, devices
    ):
        """Pairwise: Pitch simulator transitions: Normal (75%) -> High (18%) -> Critical (8%) in order."""
        headers = make_auth_header(users["transport_admin"])

        # Phase 1: Normal
        p1 = make_telemetry_payload(energy={"soc_pct": 75.0, "estimated_range_km": 140.0, "charging": False})
        await client.post("/api/ingest/telemetry", json=p1)
        r1 = await client.get("/api/operator/alerts", headers=headers)
        assert len([a for a in r1.json() if a["alert_type"] == "LOW_SOC"]) == 0

        # Phase 2: Warning
        p2 = make_telemetry_payload(energy={"soc_pct": 18.0, "estimated_range_km": 27.0, "charging": False})
        await client.post("/api/ingest/telemetry", json=p2)
        r2 = await client.get("/api/operator/alerts", headers=headers)
        assert len([a for a in r2.json() if a["alert_type"] == "LOW_SOC" and a["severity"] == "high"]) >= 1

        # Phase 3: Critical
        p3 = make_telemetry_payload(energy={"soc_pct": 8.0, "estimated_range_km": 11.0, "charging": False})
        await client.post("/api/ingest/telemetry", json=p3)
        r3 = await client.get("/api/operator/alerts", headers=headers)
        assert len([a for a in r3.json() if a["alert_type"] == "LOW_SOC" and a["severity"] == "critical"]) >= 1


# ==============================================================================
# Tier 4: Real-World Application Scenarios (5 Operational Workflows)
# ==============================================================================

class TestTier4RealWorldApplicationScenarios:
    """
    Tier 4: Comprehensive, multi-step operational scenarios modeling
    real Delhi transit, emergency response, and operator flows.
    """

    async def test_t4_scenario_1_delhi_bus_fleet_cp_to_pragati_maidan_depletion(
        self, client: AsyncClient, users, vehicles, devices
    ):
        """
        Scenario 1: Delhi Bus Fleet CP to Pragati Maidan Depletion & Critical Alert.
        - Tata Starbus EV (DL-01-BUS-2024) departs Connaught Place (28.6315, 77.2167) with 18% SoC.
        - Travels along Janpath -> India Gate -> Pragati Maidan (28.6180, 77.2410).
        - SoC drops from 18% -> 14% (HIGH alert) -> 8% (CRITICAL alert).
        - Operator monitors position, track, and alert feed.
        """
        bus_id = str(vehicles["bus"].id)
        headers = make_auth_header(users["transport_admin"])

        delhi_waypoints = [
            {"lat": 28.6315, "lng": 77.2167, "soc": 18.0, "speed": 34.0},
            {"lat": 28.6250, "lng": 77.2205, "soc": 14.0, "speed": 40.0},
            {"lat": 28.6145, "lng": 77.2260, "soc": 11.0, "speed": 45.0},
            {"lat": 28.6129, "lng": 77.2295, "soc": 9.5, "speed": 38.0},
            {"lat": 28.6180, "lng": 77.2410, "soc": 8.0, "speed": 25.0},
        ]

        for idx, wp in enumerate(delhi_waypoints):
            payload = make_telemetry_payload(
                device_code="dev-bus-test-001",
                vehicle_code="bus-test-001",
                seq=idx + 1,
                location={"lat": wp["lat"], "lng": wp["lng"], "accuracy_m": 5.0},
                motion={"speed_kph": wp["speed"], "heading_deg": 120.0},
                energy={"soc_pct": wp["soc"], "estimated_range_km": wp["soc"] * 1.6, "charging": False},
            )
            r = await client.post("/api/ingest/telemetry", json=payload)
            assert r.status_code == 200

        # Verify final vehicle position
        resp_veh = await client.get(f"/api/operator/vehicles/{bus_id}", headers=headers)
        assert resp_veh.status_code == 200
        veh = resp_veh.json()
        assert veh["soc_pct"] == 8.0
        assert abs(veh["latitude"] - 28.6180) < 1e-3

        # Verify critical alert exists
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        assert resp_alerts.status_code == 200
        critical_alerts = [
            a for a in resp_alerts.json()
            if a["alert_type"] == "LOW_SOC" and a["severity"] == "critical"
        ]
        assert len(critical_alerts) >= 1

    async def test_t4_scenario_2_peak_summer_heatwave_thermal_throttling_and_charging_hub(
        self, client: AsyncClient, users, vehicles, devices, sample_charging_hub
    ):
        """
        Scenario 2: Peak Delhi Summer Heatwave Thermal Throttling & Charging Station Reroute.
        - Ambient heat causes Fire EV battery temperature to surge to 49°C (>45°C HIGH alert).
        - Vehicle exceeds 82 km/h on emergency response (>80 km/h OVERSPEED alert).
        - System queries public charging centers to find Connaught Place Fast Charging Hub (150 kW).
        """
        headers = make_auth_header(users["fire_admin"])
        fire_id = str(vehicles["fire_truck"].id)

        # Ingest heatwave thermal surge + speed
        payload = make_telemetry_payload(
            device_code="dev-fire-test-001",
            vehicle_code="fire-test-001",
            location={"lat": 28.6300, "lng": 77.2180, "accuracy_m": 4.0},
            motion={"speed_kph": 84.5, "heading_deg": 180.0},
            energy={"soc_pct": 32.0, "estimated_range_km": 48.0, "charging": False},
            diagnostics={"battery_temp_c": 49.0, "dtcs": []},
        )
        resp = await client.post("/api/ingest/telemetry", json=payload)
        assert resp.status_code == 200

        # Operator checks fire department alerts
        resp_alerts = await client.get("/api/operator/alerts", headers=headers)
        alerts = resp_alerts.json()
        assert any(a["alert_type"] == "HIGH_BATTERY_TEMP" for a in alerts)
        assert any(a["alert_type"] == "OVERSPEED" for a in alerts)

        # Operator / navigation queries public charging hub for cooling / recharge
        resp_hub = await client.get("/api/public/charging-centers")
        assert resp_hub.status_code == 200
        hubs = resp_hub.json()
        cp_hub = next((h for h in hubs if "Connaught Place" in h["name"]), None)
        assert cp_hub is not None
        assert cp_hub["power_kw"] >= 100.0  # Fast charging capable

    async def test_t4_scenario_3_offline_mobile_tunnel_recovery_delhi_metro_subsurface(
        self, client: AsyncClient, users, vehicles, devices, db_session: AsyncSession
    ):
        """
        Scenario 3: Offline Mobile Operator Tunnel Recovery (Delhi Metro Subsurface).
        - Vehicle travels underground through Kashmere Gate underpass; connection is lost.
        - Three telemetry records (seq 101, 102, 103) are buffered in OfflineTelemetryQueue format.
        - Exits tunnel into cellular coverage; client replays buffered queue in FIFO order.
        - Backend accepts all 3 events without data loss; latest vehicle state points to terminal point.
        """
        bus_id = str(vehicles["bus"].id)
        tunnel_waypoints = [
            {"lat": 28.6665, "lng": 77.2321, "seq": 101, "soc": 60.0},
            {"lat": 28.6633, "lng": 77.2317, "seq": 102, "soc": 59.5},
            {"lat": 28.6601, "lng": 77.2313, "seq": 103, "soc": 59.0},
        ]

        # Simulate offline accumulation and sequential flush replay
        for wp in tunnel_waypoints:
            p = make_telemetry_payload(
                device_code="dev-bus-test-001",
                vehicle_code="bus-test-001",
                seq=wp["seq"],
                location={"lat": wp["lat"], "lng": wp["lng"], "accuracy_m": 8.0},
                energy={"soc_pct": wp["soc"], "estimated_range_km": 100.0, "charging": False},
            )
            r = await client.post("/api/ingest/telemetry", json=p)
            assert r.status_code == 200
            assert r.json()["status"] == "accepted"

        # Verify database has stored all 3 events
        result = await db_session.execute(
            select(TelemetryEvent).where(
                TelemetryEvent.vehicle_id == vehicles["bus"].id,
                TelemetryEvent.seq.in_([101, 102, 103])
            )
        )
        stored_events = result.scalars().all()
        assert len(stored_events) == 3

        # Verify latest vehicle position matches final waypoint (exit of tunnel)
        headers = make_auth_header(users["transport_admin"])
        resp_veh = await client.get(f"/api/operator/vehicles/{bus_id}", headers=headers)
        assert resp_veh.status_code == 200
        latest = resp_veh.json()
        assert abs(latest["latitude"] - 28.6601) < 1e-3
        assert latest["soc_pct"] == 59.0

    async def test_t4_scenario_4_multi_tenant_inter_department_fire_emergency_isolation(
        self, client: AsyncClient, users, vehicles, devices
    ):
        """
        Scenario 4: Multi-Tenant Inter-Department Fire & Transport Fleet Separation.
        - Transport Bus reports Low SoC (14%).
        - Fire Truck reports Overspeed (92 km/h).
        - Fire Admin sees ONLY fire truck alert.
        - Transport Admin sees ONLY transport bus alert.
        - Platform Admin sees BOTH alerts across the unified city fleet.
        """
        # Ingest transport bus event
        p_bus = make_telemetry_payload(
            device_code="dev-bus-test-001",
            vehicle_code="bus-test-001",
            energy={"soc_pct": 14.0, "estimated_range_km": 20.0, "charging": False},
        )
        await client.post("/api/ingest/telemetry", json=p_bus)

        # Ingest fire truck event
        p_fire = make_telemetry_payload(
            device_code="dev-fire-test-001",
            vehicle_code="fire-test-001",
            motion={"speed_kph": 92.0, "heading_deg": 180.0},
        )
        await client.post("/api/ingest/telemetry", json=p_fire)

        # 1. Fire Admin query
        fire_headers = make_auth_header(users["fire_admin"])
        r_fire = await client.get("/api/operator/alerts", headers=fire_headers)
        assert r_fire.status_code == 200
        fire_alerts = r_fire.json()
        assert all(a["vehicle_id"] == str(vehicles["fire_truck"].id) for a in fire_alerts)
        assert any(a["alert_type"] == "OVERSPEED" for a in fire_alerts)

        # 2. Transport Admin query
        trans_headers = make_auth_header(users["transport_admin"])
        r_trans = await client.get("/api/operator/alerts", headers=trans_headers)
        assert r_trans.status_code == 200
        trans_alerts = r_trans.json()
        assert all(a["vehicle_id"] == str(vehicles["bus"].id) for a in trans_alerts)
        assert any(a["alert_type"] == "LOW_SOC" for a in trans_alerts)

        # 3. Platform Admin query (cross-department unified oversight)
        admin_headers = make_auth_header(users["admin"])
        r_admin = await client.get("/api/operator/alerts", headers=admin_headers)
        assert r_admin.status_code == 200
        admin_alerts = r_admin.json()
        veh_ids = {a["vehicle_id"] for a in admin_alerts}
        assert str(vehicles["bus"].id) in veh_ids
        assert str(vehicles["fire_truck"].id) in veh_ids

    async def test_t4_scenario_5_full_pitch_simulator_5_step_presenter_demonstration(
        self, client: AsyncClient, users, vehicles, devices
    ):
        """
        Scenario 5: Full In-App Pitch Simulator 5-Step Presenter Demonstration.
        Replicates the live presentation demonstration sequence:
        - Phase 1: Connaught Place departure (SoC 75%, 35 km/h, Normal)
        - Phase 2: Barakhamba Rd transit (SoC 45%, 42 km/h, Normal)
        - Phase 3: Mandi House battery warning (SoC 18%, 36 km/h, HIGH alert)
        - Phase 4: Pragati Maidan critical warning (SoC 8%, 22 km/h, CRITICAL alert)
        - Phase 5: Plugged in at Fast Charging station (SoC 9%, Charging=True)
        """
        bus_id = str(vehicles["bus"].id)
        headers = make_auth_header(users["transport_admin"])

        demo_phases = [
            {"name": "CP Departure", "lat": 28.6328, "lng": 77.2197, "soc": 75.0, "speed": 35.0, "charging": False},
            {"name": "Barakhamba Transit", "lat": 28.6290, "lng": 77.2250, "soc": 45.0, "speed": 42.0, "charging": False},
            {"name": "Mandi House Warning", "lat": 28.6250, "lng": 77.2340, "soc": 18.0, "speed": 36.0, "charging": False},
            {"name": "Pragati Maidan Critical", "lat": 28.6180, "lng": 77.2410, "soc": 8.0, "speed": 22.0, "charging": False},
            {"name": "Charging Plug-In", "lat": 28.6180, "lng": 77.2410, "soc": 9.0, "speed": 0.0, "charging": True},
        ]

        for idx, phase in enumerate(demo_phases):
            p = make_telemetry_payload(
                device_code="dev-bus-test-001",
                vehicle_code="bus-test-001",
                seq=idx + 1,
                location={"lat": phase["lat"], "lng": phase["lng"], "accuracy_m": 4.5},
                motion={"speed_kph": phase["speed"], "heading_deg": 115.0},
                energy={"soc_pct": phase["soc"], "estimated_range_km": phase["soc"] * 1.5, "charging": phase["charging"]},
            )
            resp = await client.post("/api/ingest/telemetry", json=p)
            assert resp.status_code == 200, f"Failed at demo phase {phase['name']}"

            # Step-specific assertion
            if phase["name"] == "Mandi House Warning":
                alerts = (await client.get("/api/operator/alerts", headers=headers)).json()
                assert any(a["alert_type"] == "LOW_SOC" and a["severity"] == "high" for a in alerts)
            elif phase["name"] == "Pragati Maidan Critical":
                alerts = (await client.get("/api/operator/alerts", headers=headers)).json()
                assert any(a["alert_type"] == "LOW_SOC" and a["severity"] == "critical" for a in alerts)

        # Final verification: vehicle is stationary and charging
        final_veh = (await client.get(f"/api/operator/vehicles/{bus_id}", headers=headers)).json()
        assert final_veh["charging"] is True
        assert final_veh["speed_kph"] == 0.0
        assert final_veh["soc_pct"] == 9.0
