"""Pydantic schemas for State Transitions."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import ContainerState, SuitabilityCode


class TransitionRequest(BaseModel):
    to_state: ContainerState
    suitability_code: SuitabilityCode | None = None
    requested_by: str = Field(..., min_length=1, max_length=255)
    justification: str = ""


class TransitionApproval(BaseModel):
    approved_by: str = Field(..., min_length=1, max_length=255)


class TransitionRejection(BaseModel):
    rejected_by: str = Field(..., min_length=1, max_length=255)
    reason: str = Field(..., min_length=1)


class TransitionResponse(BaseModel):
    id: str
    container_id: str
    from_state: str
    to_state: str
    suitability_code: str | None
    status: str
    requested_by: str
    approved_by: str | None
    justification: str
    rejection_reason: str | None
    requested_at: datetime
    approved_at: datetime | None

    model_config = {"from_attributes": True}
