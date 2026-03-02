"""Audit Log API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.enums import AuditAction
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogResponse

router = APIRouter(tags=["Audit"])


@router.get("/projects/{project_id}/audit", response_model=list[AuditLogResponse])
async def get_audit_trail(
    project_id: str,
    container_id: str | None = Query(None),
    action: AuditAction | None = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get the audit trail for a project, optionally filtered."""
    query = select(AuditLog).where(AuditLog.project_id == project_id)
    if container_id:
        query = query.where(AuditLog.container_id == container_id)
    if action:
        query = query.where(AuditLog.action == action.value)
    query = query.order_by(AuditLog.timestamp.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
