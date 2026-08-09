from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class DeliverableAnnotation(BaseModel):
    """A visual pin/annotation on a deliverable asset (image or video frame).

    Coordinates are stored as percentages (0-100) so they remain correct
    when the image is displayed at different sizes.
    """

    __tablename__ = "deliverable_annotations"
    __table_args__ = (
        Index("ix_da_deliverable_id", "deliverable_id"),
        Index("ix_da_agency_id", "agency_id"),
        Index("ix_da_asset_id", "asset_id"),
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
    deliverable_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deliverables.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Asset (image/video) this pin belongs to; nullable for text deliverables
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Version of the deliverable this pin was made on
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Coordinates as percentages (0.0 – 100.0)
    x_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    y_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Sequential number shown on the pin (1, 2, 3 …)
    label_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # open | resolved
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    # general | revision | approval_note
    annotation_type: Mapped[str] = mapped_column(String(30), nullable=False, default="general")
    # internal | client_visible
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="client_visible")
    # The initial annotation comment body
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<DeliverableAnnotation id={self.id} deliverable_id={self.deliverable_id} "
            f"status={self.status} visibility={self.visibility}>"
        )


class AnnotationReply(BaseModel):
    """A reply within an annotation thread."""

    __tablename__ = "annotation_replies"
    __table_args__ = (Index("ix_ar_annotation_id", "annotation_id"),)

    annotation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deliverable_annotations.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    # internal | client_visible
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="client_visible")

    def __repr__(self) -> str:
        return f"<AnnotationReply id={self.id} annotation_id={self.annotation_id}>"
