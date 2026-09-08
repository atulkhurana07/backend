from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.telemetry import TelemetryIngestPayload, TelemetryIngestResponse
from app.services.telemetry_service import process_telemetry

router = APIRouter(prefix="/api/ingest", tags=["telemetry-ingestion"])


@router.post("/telemetry", response_model=TelemetryIngestResponse)
async def ingest_telemetry(
    payload: TelemetryIngestPayload,
    db: AsyncSession = Depends(get_db),
):
    """Ingest vehicle telemetry data. Used by simulators, devices, and MQTT bridge."""
    result = await process_telemetry(db, payload)
    if result.status == "rejected":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result.message)
    return result
