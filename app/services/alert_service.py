from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func
from datetime import datetime, timezone
from typing import Optional
import uuid

from app.models.alert import Alert, AlertType, AlertSeverity, AlertStatus
from app.models.vehicle import Vehicle
from app.models.user import User
from app.schemas.telemetry import TelemetryIngestPayload


# Alert thresholds
LOW_SOC_THRESHOLD = 20.0
LOW_RANGE_THRESHOLD_KM = 30.0
OVERSPEED_THRESHOLD_KPH = 80.0
HIGH_BATTERY_TEMP_C = 45.0


async def evaluate_alerts(
    db: AsyncSession,
    vehicle: Vehicle,
    payload: TelemetryIngestPayload,
    flags: dict,
) -> list[Alert]:
    """Evaluate telemetry against alert rules and create/update alerts."""
    new_alerts: list[Alert] = []
    now = datetime.now(timezone.utc)
    
    soc = payload.energy.soc_pct if payload.energy else None
    estimated_range = payload.energy.estimated_range_km if payload.energy else None
    speed = payload.motion.speed_kph if payload.motion else None
    charging = payload.energy.charging if payload.energy else None
    battery_temp = payload.diagnostics.battery_temp_c if payload.diagnostics else None
    dtcs = payload.diagnostics.dtcs if payload.diagnostics else None
    
    # LOW_SOC
    if soc is not None and soc < LOW_SOC_THRESHOLD:
        severity = AlertSeverity.CRITICAL if soc < 10 else AlertSeverity.HIGH
        alert = await _upsert_alert(
            db, vehicle.id, AlertType.LOW_SOC, severity, now,
            metadata={"soc_pct": soc}
        )
        if alert:
            new_alerts.append(alert)
    
    # LOW_RANGE
    if estimated_range is not None and estimated_range < LOW_RANGE_THRESHOLD_KM:
        severity = AlertSeverity.HIGH if estimated_range < 10 else AlertSeverity.MEDIUM
        alert = await _upsert_alert(
            db, vehicle.id, AlertType.LOW_RANGE, severity, now,
            metadata={"estimated_range_km": estimated_range}
        )
        if alert:
            new_alerts.append(alert)
    
    # OVERSPEED
    if speed is not None and speed > OVERSPEED_THRESHOLD_KPH:
        alert = await _upsert_alert(
            db, vehicle.id, AlertType.OVERSPEED, AlertSeverity.MEDIUM, now,
            metadata={"speed_kph": speed}
        )
        if alert:
            new_alerts.append(alert)
    
    # HIGH_BATTERY_TEMP
    if battery_temp is not None and battery_temp > HIGH_BATTERY_TEMP_C:
        severity = AlertSeverity.CRITICAL if battery_temp > 55 else AlertSeverity.HIGH
        alert = await _upsert_alert(
            db, vehicle.id, AlertType.HIGH_BATTERY_TEMP, severity, now,
            metadata={"battery_temp_c": battery_temp}
        )
        if alert:
            new_alerts.append(alert)
    
    # DIAGNOSTIC_FAULT
    if dtcs and len(dtcs) > 0:
        alert = await _upsert_alert(
            db, vehicle.id, AlertType.DIAGNOSTIC_FAULT, AlertSeverity.MEDIUM, now,
            metadata={"dtcs": dtcs}
        )
        if alert:
            new_alerts.append(alert)
    
    # CHARGING_INTERRUPTED - detect if was charging and now not, but SoC < 80
    # This is a simplified check
    if charging is False and soc is not None and soc < 80:
        # Check if there's an existing charging state
        from app.models.telemetry import TelemetryLatest
        result = await db.execute(
            select(TelemetryLatest).where(TelemetryLatest.vehicle_id == vehicle.id)
        )
        prev = result.scalar_one_or_none()
        if prev and prev.charging is True:
            alert = await _upsert_alert(
                db, vehicle.id, AlertType.CHARGING_INTERRUPTED, AlertSeverity.MEDIUM, now,
                metadata={"soc_pct": soc, "was_charging": True}
            )
            if alert:
                new_alerts.append(alert)
    
    return new_alerts


async def _upsert_alert(
    db: AsyncSession,
    vehicle_id: uuid.UUID,
    alert_type: AlertType,
    severity: AlertSeverity,
    now: datetime,
    metadata: Optional[dict] = None,
) -> Optional[Alert]:
    """Create new alert or update last_seen on existing active alert."""
    # Check for existing active/acknowledged alert of same type for this vehicle
    result = await db.execute(
        select(Alert).where(
            and_(
                Alert.vehicle_id == vehicle_id,
                Alert.alert_type == alert_type,
                Alert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]),
            )
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        existing.last_seen = now
        existing.severity = severity  # Update severity if changed
        if metadata:
            existing.metadata_ = metadata
        return None  # Not a new alert
    
    # Create new alert
    alert = Alert(
        vehicle_id=vehicle_id,
        alert_type=alert_type,
        severity=severity,
        status=AlertStatus.ACTIVE,
        first_seen=now,
        last_seen=now,
        metadata_=metadata,
    )
    db.add(alert)
    return alert


async def get_alerts_for_scope(
    db: AsyncSession,
    department_id: Optional[uuid.UUID] = None,
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Alert], int]:
    """Get alerts scoped to a department (or all for platform_admin)."""
    query = select(Alert).join(Vehicle, Alert.vehicle_id == Vehicle.id)
    count_query = select(func.count()).select_from(Alert).join(Vehicle)
    
    if department_id is not None:
        query = query.where(Vehicle.department_id == department_id)
        count_query = count_query.where(Vehicle.department_id == department_id)
    
    if status_filter:
        query = query.where(Alert.status == status_filter)
        count_query = count_query.where(Alert.status == status_filter)
    
    query = query.order_by(Alert.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    alerts = result.scalars().all()
    
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    return list(alerts), total


async def acknowledge_alert(
    db: AsyncSession,
    alert_id: uuid.UUID,
    user: User,
    department_id: Optional[uuid.UUID],
    resolution_note: Optional[str] = None,
) -> Alert:
    """Acknowledge an alert. Enforces department scope."""
    query = select(Alert).join(Vehicle).where(Alert.id == alert_id)
    if department_id is not None:
        query = query.where(Vehicle.department_id == department_id)
    
    result = await db.execute(query)
    alert = result.scalar_one_or_none()
    
    if alert is None:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found or access denied")
    
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_by = user.id
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.resolution_note = resolution_note
    
    await db.commit()
    return alert


async def broadcast_new_alert(
    department_id: uuid.UUID,
    alert: Alert,
    vehicle_code: Optional[str] = None,
) -> None:
    """Safely broadcast a newly created alert over WebSocket."""
    try:
        from app.websocket.manager import manager
        now_iso = datetime.now(timezone.utc).isoformat()
        alert_dict = {
            "id": str(alert.id),
            "vehicle_id": str(alert.vehicle_id),
            "vehicle_code": vehicle_code,
            "alert_type": alert.alert_type.value if hasattr(alert.alert_type, "value") else str(alert.alert_type),
            "severity": alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity),
            "status": alert.status.value if hasattr(alert.status, "value") else str(alert.status),
            "message": f"{alert.alert_type.value if hasattr(alert.alert_type, 'value') else alert.alert_type} alert",
            "first_seen": alert.first_seen.isoformat() if alert.first_seen else now_iso,
            "last_seen": alert.last_seen.isoformat() if alert.last_seen else now_iso,
            "metadata": alert.metadata_,
            "created_at": alert.created_at.isoformat() if getattr(alert, "created_at", None) else now_iso,
            "updated_at": alert.updated_at.isoformat() if getattr(alert, "updated_at", None) else now_iso,
        }
        await manager.broadcast_alert(department_id, alert_dict)
    except Exception as exc:
        import logging
        logging.getLogger("alert_service").warning(f"Failed to broadcast alert: {exc}")
