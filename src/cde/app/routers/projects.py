"""Project and Project Member API endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.enums import AuditAction, TransitionStatus
from app.models.project import Project, ProjectMember
from app.models.container import InformationContainer
from app.models.transition import StateTransition
from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectDashboard,
    MemberCreate,
    MemberResponse,
)
from app.services.governance import create_audit_entry

router = APIRouter(tags=["Projects"])


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    """Create a new CDE project."""
    project = Project(name=data.name, description=data.description)
    db.add(project)
    await db.flush()
    await create_audit_entry(
        db, project.id, AuditAction.PROJECT_CREATED, "system",
        details=json.dumps({"name": data.name}),
    )
    return project


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(db: AsyncSession = Depends(get_db)):
    """List all projects."""
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    return result.scalars().all()


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single project by ID."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/projects/{project_id}/dashboard", response_model=ProjectDashboard)
async def project_dashboard(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get project dashboard with container counts by state."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    containers = await db.execute(
        select(
            InformationContainer.current_state,
            func.count(InformationContainer.id),
        )
        .where(InformationContainer.project_id == project_id)
        .group_by(InformationContainer.current_state)
    )
    state_counts = {row[0]: row[1] for row in containers.all()}
    total = sum(state_counts.values())

    members = await db.execute(
        select(func.count(ProjectMember.id)).where(
            ProjectMember.project_id == project_id
        )
    )
    member_count = members.scalar() or 0

    pending = await db.execute(
        select(func.count(StateTransition.id))
        .join(InformationContainer)
        .where(
            InformationContainer.project_id == project_id,
            StateTransition.status == TransitionStatus.PENDING.value,
        )
    )
    pending_count = pending.scalar() or 0

    return ProjectDashboard(
        id=project.id,
        name=project.name,
        total_containers=total,
        containers_by_state=state_counts,
        total_members=member_count,
        pending_transitions=pending_count,
    )


# --- Project Members ---

@router.post(
    "/projects/{project_id}/members",
    response_model=MemberResponse,
    status_code=201,
)
async def add_member(
    project_id: str, data: MemberCreate, db: AsyncSession = Depends(get_db)
):
    """Add a member with a defined role to a project."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    member = ProjectMember(
        project_id=project_id,
        name=data.name,
        role=data.role.value,
    )
    db.add(member)
    await db.flush()
    await create_audit_entry(
        db, project_id, AuditAction.MEMBER_ADDED, data.name,
        details=json.dumps({"role": data.role.value}),
    )
    return member


@router.get("/projects/{project_id}/members", response_model=list[MemberResponse])
async def list_members(project_id: str, db: AsyncSession = Depends(get_db)):
    """List all members of a project."""
    result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id)
    )
    return result.scalars().all()


@router.delete("/projects/{project_id}/members/{member_id}", status_code=204)
async def remove_member(
    project_id: str, member_id: str, db: AsyncSession = Depends(get_db)
):
    """Remove a member from a project."""
    member = await db.get(ProjectMember, member_id)
    if not member or member.project_id != project_id:
        raise HTTPException(status_code=404, detail="Member not found")
    await create_audit_entry(
        db, project_id, AuditAction.MEMBER_REMOVED, member.name,
    )
    await db.delete(member)
