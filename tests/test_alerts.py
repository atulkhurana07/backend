import pytest
from datetime import datetime, timezone
from tests.conftest import make_auth_header
from app.models.alert import Alert, AlertType, AlertSeverity, AlertStatus


class TestAlerts:
    async def test_list_alerts(self, client, users, vehicles, devices, db_session):
        now = datetime.now(timezone.utc)
        alert = Alert(
            vehicle_id=vehicles["bus"].id,
            alert_type=AlertType.LOW_SOC,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.ACTIVE,
            first_seen=now,
            last_seen=now,
        )
        db_session.add(alert)
        await db_session.commit()

        headers = make_auth_header(users["transport_admin"])
        resp = await client.get("/api/operator/alerts", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["alert_type"] == "LOW_SOC"

    async def test_acknowledge_alert(self, client, users, vehicles, devices, db_session):
        now = datetime.now(timezone.utc)
        alert = Alert(
            vehicle_id=vehicles["bus"].id,
            alert_type=AlertType.OVERSPEED,
            severity=AlertSeverity.MEDIUM,
            status=AlertStatus.ACTIVE,
            first_seen=now,
            last_seen=now,
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)

        headers = make_auth_header(users["transport_admin"])
        resp = await client.post(
            f"/api/operator/alerts/{alert.id}/ack",
            headers=headers,
            json={"resolution_note": "Reviewed and resolved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "acknowledged"
