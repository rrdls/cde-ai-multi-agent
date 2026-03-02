"""Pydantic schemas for Information Containers and Revisions."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import ContainerType, ContainerState, SuitabilityCode


class ContainerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    container_type: ContainerType
    created_by: str = Field(..., min_length=1, max_length=255)


class ContainerResponse(BaseModel):
    id: str
    project_id: str
    name: str
    container_type: str
    current_state: str
    suitability_code: str | None
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ContainerDetail(ContainerResponse):
    revisions: list["RevisionResponse"] = []
    transition_count: int = 0


class RevisionResponse(BaseModel):
    id: str
    container_id: str
    revision_number: int
    original_filename: str
    file_hash: str
    file_size_bytes: int
    description: str
    uploaded_by: str
    created_at: datetime

    model_config = {"from_attributes": True}
