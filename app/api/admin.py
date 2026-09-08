from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import uuid

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, UserRole
from app.models.audit_log import AuditLog
from app.schemas.department import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from app.schemas.user import UserCreate, UserResponse, UserStatusUpdate
from app.schemas.device import DeviceCreate, DeviceResponse
from app.schemas.audit_log import AuditLogResponse
from app.services.department_service import create_department, get_departments, update_department
from app.services.user_service import create_user, get_users, update_user_status
from app.services.device_service import create_device, get_devices
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --- Departments ---

@router.get("/departments", response_model=list[DepartmentResponse])
async def list_departments(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.PLATFORM_ADMIN)),
):
    depts, total = await get_departments(db, limit, offset)
    return [DepartmentResponse.model_validate(d) for d in depts]


@router.post("/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_dept(
    body: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.PLATFORM_ADMIN)),
):
    dept = await create_department(db, body)
    await log_action(
        db, actor_id=admin.id, action="department_created",
        object_type="department", object_id=dept.id,
        metadata={"name": dept.name, "code": dept.code},
    )
    await db.commit()
    return DepartmentResponse.model_validate(dept)


@router.patch("/departments/{dept_id}", response_model=DepartmentResponse)
async def patch_department(
    dept_id: uuid.UUID,
    body: DepartmentUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.PLATFORM_ADMIN)),
):
    dept = await update_department(db, dept_id, body)
    if dept is None:
        raise HTTPException(status_code=404, detail="Department not found")
    return DepartmentResponse.model_validate(dept)


# --- Users ---

@router.get("/users", response_model=list[UserResponse])
async def list_users(
    department_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.PLATFORM_ADMIN)),
):
    users, total = await get_users(db, department_id, limit, offset)
    return [UserResponse.model_validate(u) for u in users]


@router.post("/users/invite", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def invite_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.PLATFORM_ADMIN)),
):
    user = await create_user(db, body)
    await log_action(
        db, actor_id=admin.id, action="user_created",
        object_type="user", object_id=user.id,
        metadata={"email": user.email, "role": user.role.value},
    )
    await db.commit()
    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}/status", response_model=UserResponse)
async def patch_user_status(
    user_id: uuid.UUID,
    body: UserStatusUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.PLATFORM_ADMIN)),
):
    user = await update_user_status(db, user_id, body.is_active)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    action = "user_activated" if body.is_active else "user_deactivated"
    await log_action(
        db, actor_id=admin.id, action=action,
        object_type="user", object_id=user.id,
        reason=body.reason,
    )
    await db.commit()
    return UserResponse.model_validate(user)


# --- Devices ---

@router.get("/devices", response_model=list[DeviceResponse])
async def list_devices(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.PLATFORM_ADMIN)),
):
    devices, total = await get_devices(db, limit, offset)
    return [DeviceResponse.model_validate(d) for d in devices]


@router.post("/devices", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    body: DeviceCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.PLATFORM_ADMIN)),
):
    device = await create_device(db, body)
    await log_action(
        db, actor_id=admin.id, action="device_registered",
        object_type="device", object_id=device.id,
        metadata={"device_code": device.device_code},
    )
    await db.commit()
    return DeviceResponse.model_validate(device)


# --- Audit Logs ---

@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def list_audit_logs(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.PLATFORM_ADMIN)),
):
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    )
    logs = result.scalars().all()
    return [
        AuditLogResponse(
            id=log.id,
            actor_id=log.actor_id,
            action=log.action,
            object_type=log.object_type,
            object_id=log.object_id,
            reason=log.reason,
            metadata=log.metadata_,
            ip_address=log.ip_address,
            created_at=log.created_at,
        )
        for log in logs
    ]
