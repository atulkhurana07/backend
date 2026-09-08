import pytest
from tests.conftest import make_auth_header


class TestAuth:
    async def test_login_success(self, client, users):
        resp = await client.post("/api/auth/login", json={
            "email": "admin@test.gov",
            "password": "admin123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client, users):
        resp = await client.post("/api/auth/login", json={
            "email": "admin@test.gov",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    async def test_login_inactive_user(self, client, users):
        resp = await client.post("/api/auth/login", json={
            "email": "inactive@test.gov",
            "password": "inactive123",
        })
        assert resp.status_code == 403

    async def test_me_endpoint(self, client, users):
        headers = make_auth_header(users["admin"])
        resp = await client.get("/api/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "admin@test.gov"
        assert data["role"] == "platform_admin"

    async def test_no_token_rejected(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code in (401, 403)

    async def test_refresh_token(self, client, users):
        # First login
        resp = await client.post("/api/auth/login", json={
            "email": "admin@test.gov",
            "password": "admin123",
        })
        refresh_token = resp.json()["refresh_token"]
        # Use refresh
        resp2 = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert resp2.status_code == 200
        assert "access_token" in resp2.json()
