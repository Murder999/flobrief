from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class CalendarItem(BaseModel):
    """A scheduled piece of content on the agency calendar."""

    __tablename__ = "calendar_items"
    __table_args__ = (
        Index("ix_cal_agency_id", "agency_id"),
        Index("ix_cal_brand_id", "brand_id"),
        Index("ix_cal_publish_at", "publish_at"),
        Index("ix_cal_status", "status"),
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
    brief_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("briefs.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_type: Mapped[str] = mapped_column(String(30), nullable=False, default="post")
    platform: Mapped[str] = mapped_column(String(30), nullable=False, default="other")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="planned")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    # Set only for meeting/custom items that represent a brief-lifecycle milestone
    # (CalendarMilestoneType value); null for ordinary content items.
    milestone_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    color_label: Mapped[str | None] = mapped_column(String(30), nullable=True)
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
        return f"<CalendarItem id={self.id} title={self.title!r} status={self.status}>"


class CalendarItemAsset(BaseModel):
    """Junction: attaches an asset to a calendar item."""

    __tablename__ = "calendar_item_assets"
    __table_args__ = (Index("ix_cia_calendar_item_id", "calendar_item_id"),)

    calendar_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calendar_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )


class CalendarItemAssignee(BaseModel):
    """Junction: assigns a user to a calendar item."""

    __tablename__ = "calendar_item_assignees"
    __table_args__ = (Index("ix_ciasgn_calendar_item_id", "calendar_item_id"),)

    calendar_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calendar_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )


class CalendarItemStatusHistory(BaseModel):
    """Immutable audit trail of status changes on a calendar item."""

    __tablename__ = "calendar_item_status_history"
    __table_args__ = (Index("ix_cish_calendar_item_id", "calendar_item_id"),)

    calendar_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calendar_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    old_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
