"""AuditLog model for CDE traceability."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AuditLog(Base):
    """Immutable audit trail entry.

    Every significant action in the CDE is recorded for ISO 19650 traceability.
    Entries are append-only and never modified or deleted.
    """

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    container_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("information_containers.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str] = mapped_column(Text, default="{}")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    project: Mapped["Project"] = relationship(back_populates="audit_logs")
