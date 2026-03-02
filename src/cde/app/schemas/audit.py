"""Pydantic schemas for Audit Log."""

from datetime import datetime

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: str
    project_id: str
    container_id: str | None
    action: str
    actor_name: str
    details: str
    timestamp: datetime

    model_config = {"from_attributes": True}
