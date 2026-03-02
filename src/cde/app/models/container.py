"""InformationContainer and ContainerRevision models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InformationContainer(Base):
    """An information container within the CDE.

    Represents any managed unit of information (IFC model, document,
    spreadsheet, report). Each container has a governance state that
    follows the ISO 19650 lifecycle: WIP -> Shared -> Published -> Archived.
    """

    __tablename__ = "information_containers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    container_type: Mapped[str] = mapped_column(String(50), nullable=False)
    current_state: Mapped[str] = mapped_column(String(20), default="wip")
    suitability_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    project: Mapped["Project"] = relationship(back_populates="containers")
    revisions: Mapped[list["ContainerRevision"]] = relationship(
        back_populates="container", cascade="all, delete-orphan",
        order_by="ContainerRevision.revision_number"
    )
    transitions: Mapped[list["StateTransition"]] = relationship(
        back_populates="container", cascade="all, delete-orphan"
    )


class ContainerRevision(Base):
    """A specific version of an information container's file content.

    New revisions can only be uploaded when the container is in WIP state.
    Each revision stores a SHA-256 hash for integrity verification.
    """

    __tablename__ = "container_revisions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    container_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("information_containers.id"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    uploaded_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    container: Mapped["InformationContainer"] = relationship(back_populates="revisions")
