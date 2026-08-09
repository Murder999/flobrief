from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class WorkAllocation(BaseModel):
    """A planned block of a user's time against a brief/task/deliverable, or
    a brief/task-less "general capacity block" for internal ops time — valid
    on purpose, no constraint forces brief_id/task_id/deliverable_id to be
    set. Manual, `locked=True` allocations always win over auto-derived
    planning numbers for that specific (user, entity) pair; see the
    Phase 2 `CapacityCalculationService` for the full precedence rule."""

    __tablename__ = "work_allocations"
    __table_args__ = (
        Index("ix_work_allocation_agency_id", "agency_id"),
        Index("ix_work_allocation_user_id", "user_id"),
        Index("ix_work_allocation_brief_id", "brief_id"),
        Index("ix_work_allocation_brand_id", "brand_id"),
        Index("ix_work_allocation_start_date", "start_date"),
        CheckConstraint("end_date >= start_date", name="ck_work_allocation_end_after_start"),
        CheckConstraint("allocated_minutes > 0", name="ck_work_allocation_minutes_positive"),
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
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brief_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    deliverable_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deliverables.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    allocated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    allocation_source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<WorkAllocation id={self.id} user_id={self.user_id} "
            f"allocated_minutes={self.allocated_minutes}>"
        )
