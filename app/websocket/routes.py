from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError
from typing import Optional
import uuid

from app.core.security import decode_token
from app.websocket.manager import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/operator")
async def operator_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """WebSocket endpoint for realtime operator updates.
    
    Connect with: ws://host/ws/operator?token=<jwt_access_token>
    
    The backend authenticates the token and ensures the user
    only receives updates for their authorized department.
    """
    if not token:
        await websocket.close(code=4001, reason="Token required")
        return
    
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001, reason="Invalid token type")
            return
        user_role = payload.get("role", "")
        dept_id_str = payload.get("department_id")
        department_id = uuid.UUID(dept_id_str) if dept_id_str else None
    except (JWTError, ValueError):
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    await manager.connect(websocket, user_role, department_id)
    
    try:
        while True:
            # Keep connection alive; clients can send pings
            data = await websocket.receive_text()
            # Could handle client messages here (e.g., subscribe to specific vehicles)
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_role, department_id)
