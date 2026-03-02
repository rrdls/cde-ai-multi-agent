"""Pydantic schemas for Projects and Members."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import MemberRole


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectDashboard(BaseModel):
    id: str
    name: str
    total_containers: int
    containers_by_state: dict[str, int]
    total_members: int
    pending_transitions: int


class MemberCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    role: MemberRole


class MemberResponse(BaseModel):
    id: str
    project_id: str
    name: str
    role: str

    model_config = {"from_attributes": True}
