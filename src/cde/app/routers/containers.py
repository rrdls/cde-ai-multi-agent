"""Information Container and Revision API endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.enums import ContainerState, ContainerType, AuditAction
from app.models.project import Project
from app.models.container import InformationContainer, ContainerRevision
from app.models.transition import StateTransition
from app.schemas.container import (
    ContainerCreate,
    ContainerResponse,
    ContainerDetail,
    RevisionResponse,
)
from app.services.governance import create_audit_entry
from app.services.storage import save_file, get_file_path

router = APIRouter(tags=["Containers"])


@router.post(
    "/projects/{project_id}/containers",
    response_model=ContainerResponse,
    status_code=201,
)
async def create_container(
    project_id: str, data: ContainerCreate, db: AsyncSession = Depends(get_db)
):
    """Create a new information container in WIP state."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    container = InformationContainer(
        project_id=project_id,
        name=data.name,
        container_type=data.container_type.value,
        current_state=ContainerState.WIP.value,
        created_by=data.created_by,
    )
    db.add(container)
    await db.flush()
    await create_audit_entry(
        db, project_id, AuditAction.CONTAINER_CREATED, data.created_by,
        container_id=container.id,
        details=json.dumps({"name": data.name, "type": data.container_type.value}),
    )
    return container


@router.get("/projects/{project_id}/containers", response_model=list[ContainerResponse])
async def list_containers(
    project_id: str,
    state: ContainerState | None = Query(None),
    container_type: ContainerType | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List containers in a project, optionally filtered by state or type."""
    query = select(InformationContainer).where(
        InformationContainer.project_id == project_id
    )
    if state:
        query = query.where(InformationContainer.current_state == state.value)
    if container_type:
        query = query.where(
            InformationContainer.container_type == container_type.value
        )
    query = query.order_by(InformationContainer.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/containers/{container_id}", response_model=ContainerDetail)
async def get_container(container_id: str, db: AsyncSession = Depends(get_db)):
    """Get container details with revisions."""
    result = await db.execute(
        select(InformationContainer)
        .options(selectinload(InformationContainer.revisions))
        .where(InformationContainer.id == container_id)
    )
    container = result.scalars().first()
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")

    transition_count = await db.execute(
        select(func.count(StateTransition.id)).where(
            StateTransition.container_id == container_id
        )
    )

    return ContainerDetail(
        id=container.id,
        project_id=container.project_id,
        name=container.name,
        container_type=container.container_type,
        current_state=container.current_state,
        suitability_code=container.suitability_code,
        created_by=container.created_by,
        created_at=container.created_at,
        revisions=[RevisionResponse.model_validate(r) for r in container.revisions],
        transition_count=transition_count.scalar() or 0,
    )


@router.get("/containers/{container_id}/revisions", response_model=list[RevisionResponse])
async def list_revisions(container_id: str, db: AsyncSession = Depends(get_db)):
    """List all revisions of a container."""
    result = await db.execute(
        select(ContainerRevision)
        .where(ContainerRevision.container_id == container_id)
        .order_by(ContainerRevision.revision_number)
    )
    return result.scalars().all()


@router.post(
    "/containers/{container_id}/revisions",
    response_model=RevisionResponse,
    status_code=201,
)
async def upload_revision(
    container_id: str,
    file: UploadFile = File(...),
    description: str = Form(""),
    uploaded_by: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a new file revision. Only allowed when container is in WIP state."""
    result = await db.execute(
        select(InformationContainer).where(
            InformationContainer.id == container_id
        )
    )
    container = result.scalars().first()
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")

    if container.current_state != ContainerState.WIP.value:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot upload revisions when container is in "
            f"'{container.current_state}' state. Only WIP containers accept new revisions.",
        )

    rev_count = await db.execute(
        select(func.count(ContainerRevision.id)).where(
            ContainerRevision.container_id == container_id
        )
    )
    next_rev = (rev_count.scalar() or 0) + 1

    file_path, file_hash, file_size = await save_file(
        container.project_id, container_id, next_rev, file
    )

    revision = ContainerRevision(
        container_id=container_id,
        revision_number=next_rev,
        original_filename=file.filename,
        file_path=file_path,
        file_hash=file_hash,
        file_size_bytes=file_size,
        description=description,
        uploaded_by=uploaded_by,
    )
    db.add(revision)
    await db.flush()
    await create_audit_entry(
        db, container.project_id, AuditAction.REVISION_UPLOADED, uploaded_by,
        container_id=container_id,
        details=json.dumps({
            "revision": next_rev,
            "filename": file.filename,
            "size_bytes": file_size,
            "hash": file_hash,
        }),
    )
    return revision


@router.get("/containers/{container_id}/revisions/{revision_number}/download")
async def download_revision(
    container_id: str, revision_number: int, db: AsyncSession = Depends(get_db)
):
    """Download a specific revision's file."""
    result = await db.execute(
        select(ContainerRevision).where(
            ContainerRevision.container_id == container_id,
            ContainerRevision.revision_number == revision_number,
        )
    )
    revision = result.scalars().first()
    if not revision:
        raise HTTPException(status_code=404, detail="Revision not found")

    path = get_file_path(revision.file_path)
    return FileResponse(
        path=str(path),
        filename=revision.original_filename,
        media_type="application/octet-stream",
    )
