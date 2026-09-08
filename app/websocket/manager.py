from fastapi import WebSocket
from typing import Optional
import uuid
import json


class ConnectionManager:
    """Manages WebSocket connections with department-level isolation."""
    
    def __init__(self):
        # department_id -> list of connections
        self._department_connections: dict[uuid.UUID, list[WebSocket]] = {}
        # Platform admin connections (receive everything)
        self._admin_connections: list[WebSocket] = []
    
    async def connect(
        self, websocket: WebSocket, user_role: str, department_id: Optional[uuid.UUID]
    ):
        await websocket.accept()
        if user_role == "platform_admin":
            self._admin_connections.append(websocket)
        elif department_id:
            if department_id not in self._department_connections:
                self._department_connections[department_id] = []
            self._department_connections[department_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, user_role: str, department_id: Optional[uuid.UUID]):
        if user_role == "platform_admin":
            if websocket in self._admin_connections:
                self._admin_connections.remove(websocket)
        elif department_id and department_id in self._department_connections:
            if websocket in self._department_connections[department_id]:
                self._department_connections[department_id].remove(websocket)
    
    async def broadcast_telemetry(
        self, department_id: uuid.UUID, data: dict
    ):
        """Send telemetry update to relevant connections only."""
        message = json.dumps({"type": "telemetry_update", "data": data}, default=str)
        
        dept_key = uuid.UUID(str(department_id)) if department_id else None
        
        # Send to department-specific connections
        if dept_key and dept_key in self._department_connections:
            dead = []
            for ws in self._department_connections[dept_key]:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._department_connections[dept_key].remove(ws)
        
        # Send to all admin connections
        dead_admins = []
        for ws in self._admin_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead_admins.append(ws)
        for ws in dead_admins:
            self._admin_connections.remove(ws)
    
    async def broadcast_alert(
        self, department_id: uuid.UUID, data: dict
    ):
        """Send alert notification to relevant connections only."""
        message = json.dumps({"type": "alert", "data": data}, default=str)
        
        dept_key = uuid.UUID(str(department_id)) if department_id else None
        
        if dept_key and dept_key in self._department_connections:
            dead = []
            for ws in self._department_connections[dept_key]:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._department_connections[dept_key].remove(ws)
        
        dead_admins = []
        for ws in self._admin_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead_admins.append(ws)
        for ws in dead_admins:
            self._admin_connections.remove(ws)


# Singleton instance
manager = ConnectionManager()
