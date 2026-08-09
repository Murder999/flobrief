from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class DeliverablePreviewConfig(BaseModel):
    """Platform-preview metadata for one deliverable (Social Media Preview Center).

    One row per deliverable. Editable only while the parent deliverable is in
    ``draft``/``revision_requested`` (enforced in the router, mirroring the
    same guard ``update_deliverable`` already applies) — this is the
    anti-carryover mechanism: a brand can only approve while the deliverable
    is ``submitted``, so caption/creative can never silently change on an
    already-approved deliverable.
    """

    __tablename__ = "deliverable_preview_configs"
    __table_args__ = (
        Index("ix_dpc_deliverable_id", "deliverable_id"),
        Index("ix_dpc_agency_id", "agency_id"),
        UniqueConstraint("deliverable_id", name="uq_dpc_deliverable_id"),
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
    # instagram | facebook | tiktok | linkedin | x (subset of CalendarPlatform)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    # feed_single | feed_carousel | story | reel | reel_cover | grid |
    # document_carousel | text_post (PreviewFormat)
    preview_format: Mapped[str] = mapped_column(String(30), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cta_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    hashtags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    display_name_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_photo_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    cover_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Audit marker only, incremented on every update — not load-bearing for
    # the anti-carryover guard (that relies purely on deliverable.status).
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<DeliverablePreviewConfig deliverable_id={self.deliverable_id} "
            f"platform={self.platform} preview_format={self.preview_format}>"
        )


class DeliverablePreviewSlot(BaseModel):
    """Carousel/grid slide ordering + cover flag for a deliverable's assets.

    Deliberately a dedicated table rather than columns on ``AssetLink``:
    ``AssetLink`` is a widely shared junction (briefs/comments/calendar
    items) and adding preview-only concerns (``position``, ``is_cover``)
    there would conflate unrelated consumers with zero benefit. Per-slide
    zoom is intentionally not persisted here — that's a client-only view
    control, consistent with "grid reorder is presentation-only".
    """

    __tablename__ = "deliverable_preview_slots"
    __table_args__ = (
        Index("ix_dps_deliverable_id", "deliverable_id"),
        UniqueConstraint("deliverable_id", "asset_id", name="uq_dps_deliverable_asset"),
    )

    deliverable_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deliverables.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_cover: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return (
            f"<DeliverablePreviewSlot deliverable_id={self.deliverable_id} "
            f"asset_id={self.asset_id} position={self.position}>"
        )
