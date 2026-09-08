import pytest
import asyncio
import uuid
from decimal import Decimal
from datetime import datetime, timezone, date, time
from unittest.mock import AsyncMock, patch
from starlette.websockets import WebSocketDisconnect

from tests.test_telemetry import make_telemetry_payload
from app.websocket.manager import ConnectionManager, manager


class TestWebSocketStressAndResilience:
    """Adversarial stress and resilience test harness for WebSocket broadcasting."""

    @pytest.mark.asyncio
    async def test_stress_high_frequency_telemetry_ingestion(self, client, vehicles, devices):
        """Stress-test high frequency telemetry ingestion pipeline.
        
        Rapidly fires 25 consecutive telemetry events.
        Verifies zero unhandled 500 errors, proper broadcast dispatching, and acceptance.
        """
        bus = vehicles["bus"]
        device = devices["bus_device"]

        with patch.object(manager, "broadcast_telemetry", new_callable=AsyncMock) as mock_broadcast:
            for i in range(25):
                payload = make_telemetry_payload(
                    device_id=device.device_code,
                    vehicle_id=bus.vehicle_code,
                    location={"lat": 28.6139 + (i * 0.0001), "lng": 77.2090 + (i * 0.0001), "accuracy_m": 5.0},
                    motion={"speed_kph": 30.0 + (i % 20), "heading_deg": (i * 10.0) % 360},
                    energy={"soc_pct": max(10.0, 90.0 - i), "estimated_range_km": 150.0 - i, "charging": False},
                    diagnostics={"battery_temp_c": 30.0 + (i * 0.1), "dtcs": [f"P0{i:03d}"]},
                    seq=1000 + i,
                )
                resp = await client.post("/api/ingest/telemetry", json=payload)
                assert resp.status_code == 200, f"Request {i} failed with {resp.status_code}: {resp.text}"
                body = resp.json()
                assert body["status"] == "accepted"
                assert body["event_id"] == payload["event_id"]

            assert mock_broadcast.call_count == 25

    @pytest.mark.asyncio
    async def test_stress_high_concurrency_websocket_broadcasts(self):
        """Stress-test high concurrency on ConnectionManager broadcast routines.
        
        Executes 50 simultaneous broadcast_telemetry and broadcast_alert calls
        across 20 connected clients (10 department, 10 admin) using asyncio.gather.
        """
        cm = ConnectionManager()
        dept_id = uuid.uuid4()

        dept_clients = [AsyncMock() for _ in range(10)]
        admin_clients = [AsyncMock() for _ in range(10)]

        cm._department_connections[dept_id] = list(dept_clients)
        cm._admin_connections = list(admin_clients)

        async def send_telemetry(idx):
            data = {
                "vehicle_id": str(uuid.uuid4()),
                "speed_kph": 20.0 + idx,
                "timestamp": datetime.now(timezone.utc),
            }
            await cm.broadcast_telemetry(dept_id, data)

        async def send_alert(idx):
            data = {
                "id": str(uuid.uuid4()),
                "alert_type": "LOW_SOC",
                "severity": "critical",
            }
            await cm.broadcast_alert(dept_id, data)

        # 25 telemetry + 25 alert concurrent broadcasts
        tasks = [send_telemetry(i) for i in range(25)] + [send_alert(i) for i in range(25)]
        await asyncio.gather(*tasks)

        # Every healthy client must have received all 50 messages
        for c in dept_clients:
            assert c.send_text.call_count == 50
        for c in admin_clients:
            assert c.send_text.call_count == 50

    @pytest.mark.asyncio
    async def test_client_abrupt_disconnect_during_broadcast(self):
        """Adversarial test: Clients disconnect / drop with various network exceptions during broadcast.
        
        Verifies:
        1. Dead connections are automatically pruned from connection pools.
        2. Surviving connections receive the broadcast message.
        3. broadcast_telemetry never raises an unhandled exception to callers.
        4. Subsequent broadcasts only send to surviving connections.
        """
        cm = ConnectionManager()
        dept_id = uuid.uuid4()

        # 5 healthy dept clients, 5 failing dept clients
        healthy_dept_clients = [AsyncMock() for _ in range(5)]
        failing_dept_clients = [
            AsyncMock(send_text=AsyncMock(side_effect=WebSocketDisconnect(code=1006))),
            AsyncMock(send_text=AsyncMock(side_effect=ConnectionResetError("Connection reset by peer"))),
            AsyncMock(send_text=AsyncMock(side_effect=BrokenPipeError("Broken pipe"))),
            AsyncMock(send_text=AsyncMock(side_effect=RuntimeError("Client disconnected abruptly"))),
            AsyncMock(send_text=AsyncMock(side_effect=Exception("Generic transport fault"))),
        ]

        all_dept_clients = healthy_dept_clients + failing_dept_clients
        cm._department_connections[dept_id] = list(all_dept_clients)

        # 3 healthy admin clients, 3 failing admin clients
        healthy_admin_clients = [AsyncMock() for _ in range(3)]
        failing_admin_clients = [
            AsyncMock(send_text=AsyncMock(side_effect=WebSocketDisconnect(code=1001))),
            AsyncMock(send_text=AsyncMock(side_effect=ConnectionResetError("Admin dropped"))),
            AsyncMock(send_text=AsyncMock(side_effect=TimeoutError("Admin send timeout"))),
        ]

        all_admin_clients = healthy_admin_clients + failing_admin_clients
        cm._admin_connections = list(all_admin_clients)

        # Execute broadcast - MUST NOT RAISE
        payload = {"vehicle_id": str(uuid.uuid4()), "speed_kph": 50.0}
        await cm.broadcast_telemetry(dept_id, payload)

        # Verify pruning
        assert len(cm._department_connections[dept_id]) == 5
        for client in healthy_dept_clients:
            assert client in cm._department_connections[dept_id]
            client.send_text.assert_called_once()

        for client in failing_dept_clients:
            assert client not in cm._department_connections[dept_id]

        assert len(cm._admin_connections) == 3
        for client in healthy_admin_clients:
            assert client in cm._admin_connections
            client.send_text.assert_called_once()

        for client in failing_admin_clients:
            assert client not in cm._admin_connections

        # Subsequent broadcast should only touch the remaining 8 clients
        for c in healthy_dept_clients + healthy_admin_clients:
            c.reset_mock()

        await cm.broadcast_telemetry(dept_id, {"msg": "second_burst"})
        for c in healthy_dept_clients + healthy_admin_clients:
            c.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_client_abrupt_disconnect_during_alert_broadcast(self):
        """Adversarial test: Clients disconnect during alert broadcast."""
        cm = ConnectionManager()
        dept_id = uuid.uuid4()

        healthy_dept = AsyncMock()
        broken_dept = AsyncMock(send_text=AsyncMock(side_effect=ConnectionResetError("Socket broken")))
        cm._department_connections[dept_id] = [healthy_dept, broken_dept]

        healthy_admin = AsyncMock()
        broken_admin = AsyncMock(send_text=AsyncMock(side_effect=WebSocketDisconnect(code=1006)))
        cm._admin_connections = [healthy_admin, broken_admin]

        alert_data = {
            "id": str(uuid.uuid4()),
            "alert_type": "LOW_SOC",
            "severity": "critical",
            "status": "active",
        }

        # Must not raise
        await cm.broadcast_alert(dept_id, alert_data)

        # Assert broken removed, healthy retained
        assert cm._department_connections[dept_id] == [healthy_dept]
        assert cm._admin_connections == [healthy_admin]
        healthy_dept.send_text.assert_called_once()
        healthy_admin.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_stress_challenging_json_payloads_serialization(self):
        """Stress-test JSON serialization with UUIDs, datetimes, dates, None values,
        empty structures, unicode, and large arrays.
        """
        cm = ConnectionManager()
        dept_id = uuid.uuid4()
        fake_ws = AsyncMock()
        cm._department_connections[dept_id] = [fake_ws]

        challenging_payload = {
            "uuid_v4": uuid.uuid4(),
            "uuid_v1": uuid.uuid1(),
            "utc_datetime": datetime.now(timezone.utc),
            "naive_datetime": datetime(2026, 9, 4, 12, 0, 0),
            "date_obj": date(2026, 9, 4),
            "time_obj": time(14, 30, 0),
            "none_value": None,
            "empty_list": [],
            "empty_dict": {},
            "nested": {
                "sub_uuid": uuid.uuid4(),
                "deep_none": None,
                "deep_list": [None, 1, "text", uuid.uuid4()],
            },
            "decimal_value": Decimal("123.456"),
            "unicode_text": "Battery Temp: 45°C • Status: ⚡ OK",
            "large_dtc_array": [f"P{i:04d}" for i in range(500)],
        }

        # Must serialize cleanly without TypeError
        await cm.broadcast_telemetry(dept_id, challenging_payload)
        fake_ws.send_text.assert_called_once()
        import json
        sent_raw = fake_ws.send_text.call_args[0][0]
        parsed = json.loads(sent_raw)
        assert parsed["type"] == "telemetry_update"
        assert parsed["data"]["unicode_text"] == "Battery Temp: 45°C • Status: ⚡ OK"
        assert len(parsed["data"]["large_dtc_array"]) == 500
        assert parsed["data"]["none_value"] is None
        assert parsed["data"]["empty_list"] == []

        # Test alert broadcast with challenging payload
        fake_ws.reset_mock()
        await cm.broadcast_alert(dept_id, challenging_payload)
        fake_ws.send_text.assert_called_once()
        sent_alert_raw = fake_ws.send_text.call_args[0][0]
        parsed_alert = json.loads(sent_alert_raw)
        assert parsed_alert["type"] == "alert"

    @pytest.mark.asyncio
    async def test_telemetry_ingest_zero_500_on_broadcast_crash(self, client, vehicles, devices):
        """Verify zero unhandled 500 errors on telemetry ingestion even if WebSocket
        broadcasting experiences severe internal exceptions.
        """
        bus = vehicles["bus"]
        device = devices["bus_device"]

        # Case 1: broadcast_telemetry raises severe RuntimeError
        payload1 = make_telemetry_payload(
            device_id=device.device_code,
            vehicle_id=bus.vehicle_code,
            seq=5001,
        )
        with patch.object(manager, "broadcast_telemetry", side_effect=RuntimeError("Fatal socket sub-system failure")):
            resp1 = await client.post("/api/ingest/telemetry", json=payload1)
            assert resp1.status_code == 200
            assert resp1.json()["status"] == "accepted"

        # Case 2: broadcast_alert raises severe Exception when critical alert triggers
        payload2 = make_telemetry_payload(
            device_id=device.device_code,
            vehicle_id=bus.vehicle_code,
            energy={"soc_pct": 5.0, "estimated_range_km": 100.0, "charging": False},
            seq=5002,
        )
        with patch.object(manager, "broadcast_alert", side_effect=Exception("Alert broadcaster crashed")):
            resp2 = await client.post("/api/ingest/telemetry", json=payload2)
            assert resp2.status_code == 200
            assert resp2.json()["status"] == "accepted"

        # Case 3: Both broadcast_telemetry and broadcast_alert raise simultaneously
        payload3 = make_telemetry_payload(
            device_id=device.device_code,
            vehicle_id=bus.vehicle_code,
            energy={"soc_pct": 4.0, "estimated_range_km": 100.0, "charging": False},
            seq=5003,
        )
        with patch.object(manager, "broadcast_telemetry", side_effect=RuntimeError("Crash 1")), \
             patch.object(manager, "broadcast_alert", side_effect=RuntimeError("Crash 2")):
            resp3 = await client.post("/api/ingest/telemetry", json=payload3)
            assert resp3.status_code == 200
            assert resp3.json()["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_manager_connect_disconnect_lifecycle_stress(self):
        """Stress-test 100 client connections and disconnections across multiple departments."""
        cm = ConnectionManager()
        departments = [uuid.uuid4() for _ in range(5)]
        clients = []

        # Connect 100 clients
        for i in range(100):
            mock_ws = AsyncMock()
            role = "platform_admin" if (i % 10 == 0) else "dispatcher"
            dept = None if role == "platform_admin" else departments[i % len(departments)]
            await cm.connect(mock_ws, role, dept)
            clients.append((mock_ws, role, dept))
            mock_ws.accept.assert_called_once()

        # Admin count = 10, dept connections spread across 5 depts = 90 total
        assert len(cm._admin_connections) == 10
        total_dept_connections = sum(len(conns) for conns in cm._department_connections.values())
        assert total_dept_connections == 90

        # Disconnect 50 clients
        for mock_ws, role, dept in clients[:50]:
            cm.disconnect(mock_ws, role, dept)

        # Disconnect of non-existent client must not raise ValueError
        fake_ws = AsyncMock()
        cm.disconnect(fake_ws, "platform_admin", None)
        cm.disconnect(fake_ws, "dispatcher", departments[0])

        # Verify remainder
        assert len(cm._admin_connections) == 5
        remaining_dept_connections = sum(len(conns) for conns in cm._department_connections.values())
        assert remaining_dept_connections == 45

    @pytest.mark.asyncio
    async def test_broadcast_with_string_and_uuid_department_ids(self):
        """Verify broadcast handles both string and UUID department IDs identically,
        and gracefully handles None department_id (admin-only broadcast).
        """
        cm = ConnectionManager()
        dept_uuid = uuid.uuid4()
        dept_str = str(dept_uuid)

        dept_ws = AsyncMock()
        admin_ws = AsyncMock()

        cm._department_connections[dept_uuid] = [dept_ws]
        cm._admin_connections = [admin_ws]

        # 1. Broadcast using string department ID
        await cm.broadcast_telemetry(dept_str, {"test": "via_string"})
        dept_ws.send_text.assert_called_once()
        admin_ws.send_text.assert_called_once()

        dept_ws.reset_mock()
        admin_ws.reset_mock()

        # 2. Broadcast using UUID department ID
        await cm.broadcast_telemetry(dept_uuid, {"test": "via_uuid"})
        dept_ws.send_text.assert_called_once()
        admin_ws.send_text.assert_called_once()

        dept_ws.reset_mock()
        admin_ws.reset_mock()

        # 3. Broadcast with department_id=None (should only broadcast to admins)
        await cm.broadcast_telemetry(None, {"test": "admin_only"})
        dept_ws.send_text.assert_not_called()
        admin_ws.send_text.assert_called_once()
