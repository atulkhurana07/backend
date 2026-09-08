from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles, get_department_scope
from app.models.user import User, UserRole
from app.schemas.vehicle import VehicleWithTelemetryResponse
from app.schemas.alert import AlertResponse, AlertAckRequest
from app.services.vehicle_service import get_vehicles_with_telemetry, get_vehicle_by_id, get_vehicle_track
from app.services.alert_service import get_alerts_for_scope, acknowledge_alert
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/operator", tags=["operator"])

OPERATOR_ROLES = (UserRole.PLATFORM_ADMIN, UserRole.DEPARTMENT_ADMIN, UserRole.DISPATCHER, UserRole.ANALYST, UserRole.MAINTENANCE)


@router.get("/vehicles", response_model=list[VehicleWithTelemetryResponse])
async def list_vehicles(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*OPERATOR_ROLES)),
    dept_scope: Optional[uuid.UUID] = Depends(get_department_scope),
):
    rows, total = await get_vehicles_with_telemetry(db, dept_scope, limit, offset)
    result = []
    for vehicle, telemetry in rows:
        result.append(VehicleWithTelemetryResponse(
            id=vehicle.id,
            vehicle_code=vehicle.vehicle_code,
            vehicle_type=vehicle.vehicle_type.value,
            department_id=vehicle.department_id,
            is_active=vehicle.is_active,
            latitude=telemetry.latitude if telemetry else None,
            longitude=telemetry.longitude if telemetry else None,
            speed_kph=telemetry.speed_kph if telemetry else None,
            heading_deg=telemetry.heading_deg if telemetry else None,
            soc_pct=telemetry.soc_pct if telemetry else None,
            estimated_range_km=telemetry.estimated_range_km if telemetry else None,
            charging=telemetry.charging if telemetry else None,
            connectivity_status=telemetry.connectivity_status if telemetry else None,
            last_seen=telemetry.observed_at if telemetry else None,
            battery_temp_c=float(telemetry.battery_temp_c) if (telemetry and telemetry.battery_temp_c is not None) else None,
            dtcs=list(telemetry.dtcs) if (telemetry and telemetry.dtcs is not None) else None,
        ))
    return result


@router.get("/vehicles/{vehicle_id}", response_model=VehicleWithTelemetryResponse)
async def get_vehicle(
    vehicle_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*OPERATOR_ROLES)),
    dept_scope: Optional[uuid.UUID] = Depends(get_department_scope),
):
    row = await get_vehicle_by_id(db, vehicle_id, dept_scope)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found or access denied")
    vehicle, telemetry = row
    return VehicleWithTelemetryResponse(
        id=vehicle.id,
        vehicle_code=vehicle.vehicle_code,
        vehicle_type=vehicle.vehicle_type.value,
        department_id=vehicle.department_id,
        is_active=vehicle.is_active,
        latitude=telemetry.latitude if telemetry else None,
        longitude=telemetry.longitude if telemetry else None,
        speed_kph=telemetry.speed_kph if telemetry else None,
        heading_deg=telemetry.heading_deg if telemetry else None,
        soc_pct=telemetry.soc_pct if telemetry else None,
        estimated_range_km=telemetry.estimated_range_km if telemetry else None,
        charging=telemetry.charging if telemetry else None,
        connectivity_status=telemetry.connectivity_status if telemetry else None,
        last_seen=telemetry.observed_at if telemetry else None,
        battery_temp_c=float(telemetry.battery_temp_c) if (telemetry and telemetry.battery_temp_c is not None) else None,
        dtcs=list(telemetry.dtcs) if (telemetry and telemetry.dtcs is not None) else None,
    )


@router.get("/vehicles/{vehicle_id}/track")
async def get_vehicle_track_api(
    vehicle_id: uuid.UUID,
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*OPERATOR_ROLES)),
    dept_scope: Optional[uuid.UUID] = Depends(get_department_scope),
):
    events = await get_vehicle_track(db, vehicle_id, dept_scope, limit)
    if events is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found or access denied")
    return [
        {
            "observed_at": e.observed_at,
            "latitude": e.latitude,
            "longitude": e.longitude,
            "speed_kph": e.speed_kph,
            "soc_pct": e.soc_pct,
            "heading_deg": e.heading_deg,
        }
        for e in events
    ]


@router.get("/alerts", response_model=list[AlertResponse])
async def list_alerts(
    status_filter: Optional[str] = Query(None),
    statusFilter: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*OPERATOR_ROLES)),
    dept_scope: Optional[uuid.UUID] = Depends(get_department_scope),
):
    effective_status = statusFilter if statusFilter is not None else status_filter
    alerts, total = await get_alerts_for_scope(db, dept_scope, effective_status, limit, offset)
    return [
        AlertResponse(
            id=a.id,
            vehicle_id=a.vehicle_id,
            alert_type=a.alert_type.value,
            severity=a.severity.value,
            status=a.status.value,
            first_seen=a.first_seen,
            last_seen=a.last_seen,
            acknowledged_by=a.acknowledged_by,
            acknowledged_at=a.acknowledged_at,
            resolution_note=a.resolution_note,
            metadata=a.metadata_,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in alerts
    ]


@router.post("/alerts/{alert_id}/ack", response_model=AlertResponse)
async def ack_alert(
    alert_id: uuid.UUID,
    body: AlertAckRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.DEPARTMENT_ADMIN, UserRole.DISPATCHER)),
    dept_scope: Optional[uuid.UUID] = Depends(get_department_scope),
):
    alert = await acknowledge_alert(db, alert_id, current_user, dept_scope, body.resolution_note)
    await log_action(
        db, actor_id=current_user.id, action="alert_acknowledged",
        object_type="alert", object_id=alert.id,
        metadata={"alert_type": alert.alert_type.value},
    )
    await db.commit()
    return AlertResponse(
        id=alert.id,
        vehicle_id=alert.vehicle_id,
        alert_type=alert.alert_type.value,
        severity=alert.severity.value,
        status=alert.status.value,
        first_seen=alert.first_seen,
        last_seen=alert.last_seen,
        acknowledged_by=alert.acknowledged_by,
        acknowledged_at=alert.acknowledged_at,
        resolution_note=alert.resolution_note,
        metadata=alert.metadata_,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    )
