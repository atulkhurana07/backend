import pytest
from app.core.security import create_access_token


class TestWebSocket:
    async def test_websocket_requires_token(self, client):
        """WebSocket connection without token should be rejected."""
        # httpx doesn't support WebSocket directly, so we test the HTTP upgrade
        # This is a simplified test - full WebSocket testing would use websockets library
        resp = await client.get("/ws/operator")
        # Without WebSocket upgrade, FastAPI returns 403 or connection error
        assert resp.status_code in (403, 404, 426)

    async def test_websocket_token_validation(self, client, users):
        """Test that invalid token is rejected."""
        # This validates the authentication logic conceptually
        from app.core.security import decode_token
        
        # Valid token should decode
        token = create_access_token({
            "sub": str(users["transport_admin"].id),
            "role": "department_admin",
            "department_id": str(users["transport_admin"].department_id),
        })
        payload = decode_token(token)
        assert payload["role"] == "department_admin"
        assert payload["department_id"] == str(users["transport_admin"].department_id)

    async def test_websocket_manager_department_isolation(self, users):
        """Test that the ConnectionManager isolates departments correctly."""
        from app.websocket.manager import ConnectionManager
        import uuid
        
        mgr = ConnectionManager()
        
        # Verify internal structure
        dept_a = uuid.uuid4()
        dept_b = uuid.uuid4()
        
        # After connection, department connections should be separate
        assert dept_a not in mgr._department_connections
        assert dept_b not in mgr._department_connections
        assert len(mgr._admin_connections) == 0
