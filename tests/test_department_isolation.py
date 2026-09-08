import pytest
from tests.conftest import make_auth_header


class TestDepartmentIsolation:
    """Verify that department-scoped users cannot access other departments' data.
    
    This is the single most critical security test.
    A Bus Department user must NEVER see Fire Department vehicles.
    """

    async def test_transport_admin_cannot_see_fire_vehicles(
        self, client, users, vehicles, devices
    ):
        """Transport admin queries vehicles - must not see fire department vehicle."""
        headers = make_auth_header(users["transport_admin"])
        resp = await client.get("/api/operator/vehicles", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        vehicle_codes = [v["vehicle_code"] for v in data]
        assert "bus-test-001" in vehicle_codes
        assert "fire-test-001" not in vehicle_codes  # CRITICAL CHECK

    async def test_fire_admin_cannot_see_transport_vehicles(
        self, client, users, vehicles, devices
    ):
        headers = make_auth_header(users["fire_admin"])
        resp = await client.get("/api/operator/vehicles", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        vehicle_codes = [v["vehicle_code"] for v in data]
        assert "fire-test-001" in vehicle_codes
        assert "bus-test-001" not in vehicle_codes  # CRITICAL CHECK

    async def test_transport_admin_cannot_access_fire_vehicle_by_id(
        self, client, users, vehicles, devices
    ):
        """Even with the exact vehicle ID, a transport user cannot access fire vehicle."""
        headers = make_auth_header(users["transport_admin"])
        fire_id = str(vehicles["fire_truck"].id)
        resp = await client.get(f"/api/operator/vehicles/{fire_id}", headers=headers)
        assert resp.status_code == 404  # Not found (access denied)

    async def test_platform_admin_sees_all_vehicles(
        self, client, users, vehicles, devices
    ):
        """Platform admin should see vehicles from ALL departments."""
        headers = make_auth_header(users["admin"])
        resp = await client.get("/api/operator/vehicles", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        vehicle_codes = [v["vehicle_code"] for v in data]
        assert "bus-test-001" in vehicle_codes
        assert "fire-test-001" in vehicle_codes

    async def test_dispatcher_scoped_to_department(
        self, client, users, vehicles, devices
    ):
        """Dispatcher should only see their own department."""
        headers = make_auth_header(users["dispatcher"])
        resp = await client.get("/api/operator/vehicles", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        vehicle_codes = [v["vehicle_code"] for v in data]
        assert "bus-test-001" in vehicle_codes
        assert "fire-test-001" not in vehicle_codes

    async def test_transport_admin_cannot_ack_fire_alert(
        self, client, users, vehicles, devices, db_session
    ):
        """Transport admin cannot acknowledge a fire department alert."""
        from app.models.alert import Alert, AlertType, AlertSeverity, AlertStatus
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        fire_alert = Alert(
            vehicle_id=vehicles["fire_truck"].id,
            alert_type=AlertType.LOW_SOC,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.ACTIVE,
            first_seen=now,
            last_seen=now,
        )
        db_session.add(fire_alert)
        await db_session.commit()
        await db_session.refresh(fire_alert)

        headers = make_auth_header(users["transport_admin"])
        resp = await client.post(
            f"/api/operator/alerts/{fire_alert.id}/ack",
            headers=headers,
            json={"resolution_note": "Should not work"},
        )
        assert resp.status_code == 404  # Access denied
