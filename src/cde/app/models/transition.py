"""StateTransition model for governance decisions."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StateTransition(Base):
    """A governance state transition request for an information container.

    Implements the two-step human-in-the-loop pattern: a transition is first
    requested (with justification), then approved or rejected by an authorized
    actor. This preserves ISO 19650 accountability requirements.
    """

    __tablename__ = "state_transitions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    container_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("information_containers.id"), nullable=False
    )
    from_state: Mapped[str] = mapped_column(String(20), nullable=False)
    to_state: Mapped[str] = mapped_column(String(20), nullable=False)
    suitability_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    justification: Mapped[str] = mapped_column(Text, default="")
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    container: Mapped["InformationContainer"] = relationship(back_populates="transitions")
