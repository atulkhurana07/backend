from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog
from typing import Optional
import uuid


async def log_action(
    db: AsyncSession,
    *,
    actor_id: Optional[uuid.UUID],
    action: str,
    object_type: str,
    object_id: Optional[uuid.UUID] = None,
    reason: Optional[str] = None,
    metadata: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """Create an append-only audit log entry."""
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        reason=reason,
        metadata_=metadata,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
    return entry
