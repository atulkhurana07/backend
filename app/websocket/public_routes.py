from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from typing import Optional

from app.core.database import AsyncSessionLocal
from app.services.public_data_service import get_public_vehicles

router = APIRouter(prefix="/ws/public", tags=["websocket-public"])

import uuid

@router.websocket("/vehicles")
async def websocket_public_vehicles(
    websocket: WebSocket,
    city: Optional[str] = Query(None),
    vehicle_type: Optional[str] = Query(None),
    route_id: Optional[uuid.UUID] = Query(None),
):
    await websocket.accept()
    try:
        while True:
            # Re-fetch the vehicles freshly from DB per tick
            async with AsyncSessionLocal() as session:
                vehicles = await get_public_vehicles(session, vehicle_type=vehicle_type, city=city, route_id=route_id)
                # Send data to client
                await websocket.send_json([v.model_dump(mode="json") for v in vehicles])
            
            # 2 second intervals for real-time smooth tracking
            await asyncio.sleep(2)
    except (WebSocketDisconnect, ConnectionResetError, asyncio.CancelledError):
        pass
    except Exception as e:
        try:
            await websocket.close()
        except Exception:
            pass
