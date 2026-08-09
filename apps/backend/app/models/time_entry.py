from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class TimeEntry(BaseModel):
    """A single unit of tracked work time — created only via an explicit timer
    start or an explicit manual entry. Never synthesized or inferred."""

    __tablename__ = "time_entries"
    __table_args__ = (
        Index("ix_time_entry_agency_id", "agency_id"),
        Index("ix_time_entry_user_id", "user_id"),
        Index("ix_time_entry_brief_id", "brief_id"),
        Index("ix_time_entry_brand_id", "brand_id"),
        Index("ix_time_entry_started_at", "started_at"),
        Index(
            "uq_time_entry_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL AND deleted_at IS NULL"),
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at > started_at",
            name="ck_time_entry_end_after_start",
        ),
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
    deliverable_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deliverables.id", ondelete="SET NULL"),
        nullable=True,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brief_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    billable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # "timer" | "manual"
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="manual")
    # doubles as "approved" — avoids a redundant parallel approval-status string
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    locked_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Part 2 hooks — populated once, at the moment this entry is attached to
    # a ClientInvoiceLine (Phase 4), never at entry creation or lock time.
    # Once invoiced_at is set, these snapshots are immutable.
    invoiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    billing_rate_snapshot_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_rate_snapshot_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_currency_snapshot: Mapped[str | None] = mapped_column(String(3), nullable=True)

    def __repr__(self) -> str:
        return f"<TimeEntry id={self.id} user_id={self.user_id} started_at={self.started_at}>"
