import pytest
from tests.conftest import make_auth_header


class TestAdminAPI:
    async def test_admin_can_list_departments(self, client, users, departments):
        headers = make_auth_header(users["admin"])
        resp = await client.get("/api/admin/departments", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 3

    async def test_non_admin_cannot_list_departments(self, client, users, departments):
        headers = make_auth_header(users["transport_admin"])
        resp = await client.get("/api/admin/departments", headers=headers)
        assert resp.status_code == 403

    async def test_admin_can_create_department(self, client, users, departments):
        headers = make_auth_header(users["admin"])
        resp = await client.post("/api/admin/departments", headers=headers, json={
            "name": "Water Department",
            "code": "WATER",
            "description": "Water utility fleet",
        })
        assert resp.status_code == 201

    async def test_admin_can_invite_user(self, client, users, departments):
        headers = make_auth_header(users["admin"])
        resp = await client.post("/api/admin/users/invite", headers=headers, json={
            "email": "newuser@test.gov",
            "password": "newuser123",
            "full_name": "New User",
            "role": "dispatcher",
            "department_id": str(departments["transport"].id),
        })
        assert resp.status_code == 201

    async def test_admin_can_deactivate_user(self, client, users, departments):
        headers = make_auth_header(users["admin"])
        user_id = str(users["dispatcher"].id)
        resp = await client.patch(f"/api/admin/users/{user_id}/status", headers=headers, json={
            "is_active": False,
            "reason": "Testing deactivation",
        })
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_dispatcher_cannot_access_admin(self, client, users):
        headers = make_auth_header(users["dispatcher"])
        resp = await client.get("/api/admin/users", headers=headers)
        assert resp.status_code == 403

    async def test_admin_can_view_audit_logs(self, client, users, departments):
        headers = make_auth_header(users["admin"])
        resp = await client.get("/api/admin/audit-logs", headers=headers)
        assert resp.status_code == 200
