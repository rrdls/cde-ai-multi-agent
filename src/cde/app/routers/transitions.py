"""State Transition (Governance) API endpoints."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.enums import ContainerState, TransitionStatus, AuditAction
from app.models.container import InformationContainer
from app.models.transition import StateTransition
from app.schemas.transition import (
    TransitionRequest,
    TransitionApproval,
    TransitionRejection,
    TransitionResponse,
)
from app.services.governance import (
    validate_transition,
    validate_suitability_required,
    check_no_pending_transitions,
    apply_transition,
    reject_transition,
    create_audit_entry,
)

router = APIRouter(tags=["Transitions"])


@router.post(
    "/containers/{container_id}/transitions",
    response_model=TransitionResponse,
    status_code=201,
)
async def request_transition(
    container_id: str,
    data: TransitionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request a governance state transition for a container.

    This is the first step of the two-step governance process.
    The transition must be approved by an authorized actor.
    """
    result = await db.execute(
        select(InformationContainer).where(
            InformationContainer.id == container_id
        )
    )
    container = result.scalars().first()
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")

    from_state = ContainerState(container.current_state)
    validate_transition(from_state, data.to_state)
    validate_suitability_required(data.to_state, data.suitability_code and data.suitability_code.value)
    await check_no_pending_transitions(db, container_id)

    transition = StateTransition(
        container_id=container_id,
        from_state=from_state.value,
        to_state=data.to_state.value,
        suitability_code=data.suitability_code.value if data.suitability_code else None,
        status=TransitionStatus.PENDING.value,
        requested_by=data.requested_by,
        justification=data.justification,
    )
    db.add(transition)
    await db.flush()
    await create_audit_entry(
        db, container.project_id, AuditAction.TRANSITION_REQUESTED, data.requested_by,
        container_id=container_id,
        details=json.dumps({
            "from": from_state.value,
            "to": data.to_state.value,
            "suitability": data.suitability_code.value if data.suitability_code else None,
        }),
    )
    return transition


@router.get(
    "/containers/{container_id}/transitions",
    response_model=list[TransitionResponse],
)
async def list_transitions(
    container_id: str, db: AsyncSession = Depends(get_db)
):
    """List all transition history for a container."""
    result = await db.execute(
        select(StateTransition)
        .where(StateTransition.container_id == container_id)
        .order_by(StateTransition.requested_at.desc())
    )
    return result.scalars().all()


@router.post(
    "/transitions/{transition_id}/approve",
    response_model=TransitionResponse,
)
async def approve_transition_endpoint(
    transition_id: str,
    data: TransitionApproval,
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending state transition (step 2 of governance process)."""
    transition = await db.get(StateTransition, transition_id)
    if not transition:
        raise HTTPException(status_code=404, detail="Transition not found")
    if transition.status != TransitionStatus.PENDING.value:
        raise HTTPException(
            status_code=422,
            detail=f"Transition is already {transition.status}.",
        )

    container = await db.get(InformationContainer, transition.container_id)
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")

    transition.approved_by = data.approved_by
    await apply_transition(db, transition, container)
    await create_audit_entry(
        db, container.project_id, AuditAction.TRANSITION_APPROVED, data.approved_by,
        container_id=container.id,
        details=json.dumps({
            "from": transition.from_state,
            "to": transition.to_state,
            "transition_id": transition.id,
        }),
    )
    return transition


@router.post(
    "/transitions/{transition_id}/reject",
    response_model=TransitionResponse,
)
async def reject_transition_endpoint(
    transition_id: str,
    data: TransitionRejection,
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending state transition."""
    transition = await db.get(StateTransition, transition_id)
    if not transition:
        raise HTTPException(status_code=404, detail="Transition not found")
    if transition.status != TransitionStatus.PENDING.value:
        raise HTTPException(
            status_code=422,
            detail=f"Transition is already {transition.status}.",
        )

    container = await db.get(InformationContainer, transition.container_id)
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")

    transition.approved_by = data.rejected_by
    await reject_transition(db, transition, data.reason)
    await create_audit_entry(
        db, container.project_id, AuditAction.TRANSITION_REJECTED, data.rejected_by,
        container_id=container.id,
        details=json.dumps({
            "from": transition.from_state,
            "to": transition.to_state,
            "reason": data.reason,
            "transition_id": transition.id,
        }),
    )
    return transition


@router.get(
    "/projects/{project_id}/transitions/pending",
    response_model=list[TransitionResponse],
)
async def list_pending_transitions(
    project_id: str, db: AsyncSession = Depends(get_db)
):
    """List all pending transition requests for a project."""
    result = await db.execute(
        select(StateTransition)
        .join(InformationContainer)
        .where(
            InformationContainer.project_id == project_id,
            StateTransition.status == TransitionStatus.PENDING.value,
        )
        .order_by(StateTransition.requested_at.desc())
    )
    return result.scalars().all()
