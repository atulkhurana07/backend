import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from tests.conftest import make_auth_header
from tests.test_telemetry import make_telemetry_payload
from app.websocket.manager import ConnectionManager, manager


class TestRealtimeBroadcast:
    async def test_telemetry_ingest_triggers_broadcast_telemetry(
        self, client, vehicles, devices
    ):
        """Test that POST /api/ingest/telemetry triggers broadcast_telemetry over WebSocket."""
        bus = vehicles["bus"]
        payload = make_telemetry_payload(
            device_id=devices["bus_device"].device_code,
            vehicle_id=bus.vehicle_code,
            location={"lat": 28.6139, "lng": 77.2090, "accuracy_m": 5},
            motion={"speed_kph": 42.5, "heading_deg": 180.0},
            energy={"soc_pct": 75.0, "estimated_range_km": 140.0, "charging": False},
            diagnostics={"battery_temp_c": 35.5, "dtcs": ["P0A80"]},
        )

        with patch.object(manager, "broadcast_telemetry", new_callable=AsyncMock) as mock_broadcast:
            resp = await client.post("/api/ingest/telemetry", json=payload)
            assert resp.status_code == 200
            assert resp.json()["status"] == "accepted"

            mock_broadcast.assert_called_once()
            called_dept_id, broadcast_data = mock_broadcast.call_args[0]
            assert str(called_dept_id) == str(bus.department_id)
            assert broadcast_data["vehicle_id"] == str(bus.id)
            assert broadcast_data["latitude"] == 28.6139
            assert broadcast_data["longitude"] == 77.2090
            assert broadcast_data["speed_kph"] == 42.5
            assert broadcast_data["heading_deg"] == 180.0
            assert broadcast_data["soc_pct"] == 75.0
            assert broadcast_data["estimated_range_km"] == 140.0
            assert broadcast_data["charging"] is False
            assert broadcast_data["connectivity_status"] == "online"
            assert "observed_at" in broadcast_data
            assert broadcast_data["battery_temp_c"] == 35.5
            assert broadcast_data["dtcs"] == ["P0A80"]

    async def test_telemetry_broadcast_resilience_on_exception(
        self, client, vehicles, devices
    ):
        """Test that WebSocket broadcast errors do not fail telemetry ingestion responses."""
        bus = vehicles["bus"]
        payload = make_telemetry_payload(
            device_id=devices["bus_device"].device_code,
            vehicle_id=bus.vehicle_code,
        )

        with patch.object(manager, "broadcast_telemetry", side_effect=RuntimeError("WS connection dropped")):
            resp = await client.post("/api/ingest/telemetry", json=payload)
            assert resp.status_code == 200
            assert resp.json()["status"] == "accepted"

    async def test_alert_condition_triggers_broadcast_alert(
        self, client, vehicles, devices
    ):
        """Test that triggering an alert condition broadcasts the alert over WebSocket."""
        bus = vehicles["bus"]
        # soc < 10% triggers critical LOW_SOC alert (set range=100 so LOW_RANGE does not fire)
        payload = make_telemetry_payload(
            device_id=devices["bus_device"].device_code,
            vehicle_id=bus.vehicle_code,
            energy={"soc_pct": 8.0, "estimated_range_km": 100.0, "charging": False},
        )

        with patch.object(manager, "broadcast_alert", new_callable=AsyncMock) as mock_alert_broadcast:
            resp = await client.post("/api/ingest/telemetry", json=payload)
            assert resp.status_code == 200
            assert resp.json()["status"] == "accepted"

            mock_alert_broadcast.assert_called()
            called_dept_id, alert_dict = mock_alert_broadcast.call_args[0]
            assert str(called_dept_id) == str(bus.department_id)
            assert alert_dict["vehicle_id"] == str(bus.id)
            assert alert_dict["alert_type"] == "LOW_SOC"
            assert alert_dict["severity"] == "critical"
            assert alert_dict["status"] == "active"
            assert isinstance(alert_dict["id"], str)
            assert isinstance(alert_dict["created_at"], str)

    async def test_safe_json_serialization_in_manager(self):
        """Test that ConnectionManager serializes UUIDs and datetimes safely without TypeError."""
        cm = ConnectionManager()
        dept_id = uuid.uuid4()
        fake_ws = AsyncMock()

        cm._department_connections[dept_id] = [fake_ws]

        test_data = {
            "uuid": uuid.uuid4(),
            "timestamp": datetime.now(timezone.utc),
            "nested": {"id": uuid.uuid4()},
        }

        # Should not raise TypeError: Object of type UUID is not JSON serializable
        await cm.broadcast_telemetry(dept_id, test_data)
        fake_ws.send_text.assert_called_once()
        sent_text = fake_ws.send_text.call_args[0][0]
        assert "telemetry_update" in sent_text

        # Test alert broadcast serialization
        fake_ws.reset_mock()
        await cm.broadcast_alert(dept_id, test_data)
        fake_ws.send_text.assert_called_once()
        sent_alert_text = fake_ws.send_text.call_args[0][0]
        assert "alert" in sent_alert_text

    async def test_operator_vehicles_returns_diagnostics(
        self, client, users, vehicles, devices
    ):
        """Test that GET /api/operator/vehicles exposes battery_temp_c and dtcs."""
        bus = vehicles["bus"]
        payload = make_telemetry_payload(
            device_id=devices["bus_device"].device_code,
            vehicle_id=bus.vehicle_code,
            diagnostics={"battery_temp_c": 39.2, "dtcs": ["P0A80", "P0A7F"]},
        )
        # Ingest to update telemetry_latest
        await client.post("/api/ingest/telemetry", json=payload)

        headers = make_auth_header(users["transport_admin"])
        resp = await client.get("/api/operator/vehicles", headers=headers)
        assert resp.status_code == 200
        vehicles_data = resp.json()
        assert len(vehicles_data) >= 1

        target_vehicle = next((v for v in vehicles_data if v["id"] == str(bus.id)), None)
        assert target_vehicle is not None
        assert target_vehicle["battery_temp_c"] == 39.2
        assert target_vehicle["dtcs"] == ["P0A80", "P0A7F"]
        assert target_vehicle["vehicle_code"] == bus.vehicle_code
        assert target_vehicle["is_active"] is True

    async def test_operator_vehicle_by_id_returns_diagnostics(
        self, client, users, vehicles, devices
    ):
        """Test that GET /api/operator/vehicles/{id} exposes battery_temp_c and dtcs."""
        bus = vehicles["bus"]
        payload = make_telemetry_payload(
            device_id=devices["bus_device"].device_code,
            vehicle_id=bus.vehicle_code,
            diagnostics={"battery_temp_c": 41.0, "dtcs": ["P0100"]},
        )
        await client.post("/api/ingest/telemetry", json=payload)

        headers = make_auth_header(users["transport_admin"])
        resp = await client.get(f"/api/operator/vehicles/{bus.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(bus.id)
        assert data["battery_temp_c"] == 41.0
        assert data["dtcs"] == ["P0100"]

    async def test_public_vehicles_does_not_expose_diagnostics(
        self, client, vehicles, devices
    ):
        """Privacy test: verify public vehicle endpoint strictly excludes diagnostic fields."""
        bus = vehicles["bus"]
        payload = make_telemetry_payload(
            device_id=devices["bus_device"].device_code,
            vehicle_id=bus.vehicle_code,
            diagnostics={"battery_temp_c": 44.0, "dtcs": ["P0A80"]},
        )
        await client.post("/api/ingest/telemetry", json=payload)

        resp = await client.get("/api/public/vehicles")
        assert resp.status_code == 200
        data = resp.json()
        for v in data:
            assert "battery_temp_c" not in v, "Public endpoint leaked battery_temp_c"
            assert "dtcs" not in v, "Public endpoint leaked dtcs"
