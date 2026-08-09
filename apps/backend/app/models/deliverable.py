from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class Deliverable(BaseModel):
    """An agency-produced output unit for a brief — image, video, copy, etc."""

    __tablename__ = "deliverables"
    __table_args__ = (
        Index("ix_deliverable_brief_id", "brief_id"),
        Index("ix_deliverable_agency_id", "agency_id"),
    )

    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="SET NULL"),
        nullable=True,
    )
    brief_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("briefs.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    # image | video | text | document | link | other
    deliverable_type: Mapped[str] = mapped_column(String(30), nullable=False, default="other")
    # draft | submitted | revision_requested | approved | rejected | archived
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    revision_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    approve_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Deliverable id={self.id} brief_id={self.brief_id} status={self.status}>"
