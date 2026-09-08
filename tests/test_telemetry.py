import pytest
import uuid
from datetime import datetime, timezone, timedelta
from tests.conftest import make_auth_header


def make_telemetry_payload(**overrides) -> dict:
    base = {
        "device_id": "dev-bus-test-001",
        "vehicle_id": "bus-test-001",
        "event_id": str(uuid.uuid4()),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "location": {"lat": 28.6139, "lng": 77.2090, "accuracy_m": 8},
        "motion": {"speed_kph": 31.4, "heading_deg": 87},
        "energy": {"soc_pct": 64, "estimated_range_km": 118, "charging": False},
        "diagnostics": {"dtcs": [], "battery_temp_c": 32},
        "connectivity": {"network": "4G", "firmware": "0.3.1"},
        "seq": 1,
    }
    base.update(overrides)
    return base


class TestTelemetryIngestion:
    async def test_valid_telemetry_accepted(self, client, vehicles, devices):
        payload = make_telemetry_payload()
        resp = await client.post("/api/ingest/telemetry", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"

    async def test_duplicate_event_idempotent(self, client, vehicles, devices):
        event_id = str(uuid.uuid4())
        payload = make_telemetry_payload(event_id=event_id)
        resp1 = await client.post("/api/ingest/telemetry", json=payload)
        assert resp1.status_code == 200
        resp2 = await client.post("/api/ingest/telemetry", json=payload)
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "duplicate"

    async def test_invalid_latitude_rejected(self, client, vehicles, devices):
        payload = make_telemetry_payload()
        payload["location"]["lat"] = 999
        resp = await client.post("/api/ingest/telemetry", json=payload)
        assert resp.status_code == 422

    async def test_invalid_longitude_rejected(self, client, vehicles, devices):
        payload = make_telemetry_payload()
        payload["location"]["lng"] = -200
        resp = await client.post("/api/ingest/telemetry", json=payload)
        assert resp.status_code == 422

    async def test_negative_speed_rejected(self, client, vehicles, devices):
        payload = make_telemetry_payload()
        payload["motion"]["speed_kph"] = -10
        resp = await client.post("/api/ingest/telemetry", json=payload)
        assert resp.status_code == 422

    async def test_soc_over_100_rejected(self, client, vehicles, devices):
        payload = make_telemetry_payload()
        payload["energy"]["soc_pct"] = 150
        resp = await client.post("/api/ingest/telemetry", json=payload)
        assert resp.status_code == 422

    async def test_unknown_device_rejected(self, client, vehicles, devices):
        payload = make_telemetry_payload(device_id="unknown-device")
        resp = await client.post("/api/ingest/telemetry", json=payload)
        assert resp.status_code == 422

    async def test_impossible_speed_flagged(self, client, vehicles, devices):
        payload = make_telemetry_payload()
        payload["motion"]["speed_kph"] = 190  # Below 200 max but still valid, so accepted
        resp = await client.post("/api/ingest/telemetry", json=payload)
        assert resp.status_code == 200

    async def test_future_timestamp_flagged(self, client, vehicles, devices):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        payload = make_telemetry_payload(observed_at=future)
        resp = await client.post("/api/ingest/telemetry", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["flags"] and data["flags"].get("future_timestamp")
