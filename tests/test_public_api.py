import pytest


class TestPublicAPI:
    """Verify public API returns sanitized data with no sensitive info."""

    async def test_public_vehicles_no_auth_required(self, client, vehicles, devices):
        resp = await client.get("/api/public/vehicles")
        assert resp.status_code == 200

    async def test_public_vehicles_no_sensitive_fields(self, client, vehicles, devices):
        resp = await client.get("/api/public/vehicles")
        assert resp.status_code == 200
        data = resp.json()
        for vehicle in data:
            # These fields must NEVER appear in public API
            assert "registration_number" not in vehicle
            assert "device_id" not in vehicle
            assert "device_code" not in vehicle
            assert "driver_name" not in vehicle
            assert "driver_phone" not in vehicle
            assert "dtcs" not in vehicle
            assert "battery_temp_c" not in vehicle
            assert "firmware" not in vehicle
            assert "raw_payload" not in vehicle

    async def test_public_charging_centers_no_auth(self, client):
        resp = await client.get("/api/public/charging-centers")
        assert resp.status_code == 200

    async def test_public_states_and_cities(self, client):
        resp_states = await client.get("/api/public/states")
        assert resp_states.status_code == 200
        resp_cities = await client.get("/api/public/cities")
        assert resp_cities.status_code == 200

    async def test_public_routes_and_stops(self, client):
        resp_routes = await client.get("/api/public/routes")
        assert resp_routes.status_code == 200
        resp_stops = await client.get("/api/public/stops")
        assert resp_stops.status_code == 200

    async def test_public_help_contacts(self, client):
        resp = await client.get("/api/public/help-contacts")
        assert resp.status_code == 200

    async def test_public_simulation_schedule_exposes_provenance(self, client):
        resp = await client.get("/api/public/simulation/schedule")
        assert resp.status_code == 200
        data = resp.json()
        assert data["published_routes_status"] == "proposed"
        assert data["timetable_status"] == "planning_scenario_not_official"
        assert len(data["proposed_routes"]) == 25
