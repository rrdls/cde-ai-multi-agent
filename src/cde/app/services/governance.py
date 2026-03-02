"""Governance service implementing ISO 19650 state machine rules."""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ContainerState, TransitionStatus, AuditAction
from app.models.container import InformationContainer
from app.models.transition import StateTransition
from app.models.audit import AuditLog

VALID_TRANSITIONS: dict[ContainerState, list[ContainerState]] = {
    ContainerState.WIP: [ContainerState.SHARED],
    ContainerState.SHARED: [ContainerState.PUBLISHED, ContainerState.WIP],
    ContainerState.PUBLISHED: [ContainerState.ARCHIVED],
    ContainerState.ARCHIVED: [],
}


def validate_transition(from_state: ContainerState, to_state: ContainerState) -> None:
    """Check if a state transition is valid according to ISO 19650 rules."""
    allowed = VALID_TRANSITIONS.get(from_state, [])
    if to_state not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid transition: {from_state.value} -> {to_state.value}. "
            f"Allowed transitions from {from_state.value}: "
            f"{[s.value for s in allowed]}",
        )


def validate_suitability_required(
    to_state: ContainerState, suitability_code: str | None
) -> None:
    """Suitability code is required when transitioning to Shared state."""
    if to_state == ContainerState.SHARED and not suitability_code:
        raise HTTPException(
            status_code=422,
            detail="A suitability code is required when transitioning to Shared state "
            "(ISO 19650-1:2018, Table 1).",
        )


async def check_no_pending_transitions(
    db: AsyncSession, container_id: str
) -> None:
    """Ensure there are no pending transitions for this container."""
    result = await db.execute(
        select(StateTransition).where(
            StateTransition.container_id == container_id,
            StateTransition.status == TransitionStatus.PENDING.value,
        )
    )
    if result.scalars().first():
        raise HTTPException(
            status_code=409,
            detail="This container already has a pending transition request.",
        )


async def apply_transition(
    db: AsyncSession, transition: StateTransition, container: InformationContainer
) -> None:
    """Apply an approved transition: update container state and suitability."""
    container.current_state = transition.to_state
    if transition.suitability_code:
        container.suitability_code = transition.suitability_code
    transition.status = TransitionStatus.APPROVED.value
    transition.approved_at = datetime.now(timezone.utc)


async def reject_transition(
    db: AsyncSession, transition: StateTransition, reason: str
) -> None:
    """Reject a transition request."""
    transition.status = TransitionStatus.REJECTED.value
    transition.rejection_reason = reason
    transition.approved_at = datetime.now(timezone.utc)


async def create_audit_entry(
    db: AsyncSession,
    project_id: str,
    action: AuditAction,
    actor_name: str,
    container_id: str | None = None,
    details: str = "{}",
) -> AuditLog:
    """Create an immutable audit log entry."""
    entry = AuditLog(
        project_id=project_id,
        container_id=container_id,
        action=action.value,
        actor_name=actor_name,
        details=details,
    )
    db.add(entry)
    return entry
