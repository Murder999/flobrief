from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class WorkSchedule(BaseModel):
    """A user's weekly capacity template. Edits are soft-delete-old +
    insert-new (never mutated in place), so historical capacity calculations
    stay stable even after a user's schedule changes. `timezone` is a real
    IANA zone name, validated in the Pydantic schema via `zoneinfo`."""

    __tablename__ = "work_schedules"
    __table_args__ = (
        Index("ix_work_schedule_agency_id", "agency_id"),
        Index("ix_work_schedule_user_id", "user_id"),
        Index(
            "uq_work_schedule_one_active_per_user",
            "agency_id",
            "user_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Europe/Istanbul")
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)

    def __repr__(self) -> str:
        return f"<WorkSchedule id={self.id} user_id={self.user_id} timezone={self.timezone}>"


class WorkScheduleDay(BaseModel):
    """One weekday's capacity within a WorkSchedule (0=Monday .. 6=Sunday, ISO)."""

    __tablename__ = "work_schedule_days"
    __table_args__ = (
        UniqueConstraint("work_schedule_id", "weekday", name="uq_work_schedule_day_weekday"),
        Index("ix_work_schedule_day_work_schedule_id", "work_schedule_id"),
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_work_schedule_day_weekday_range"),
        CheckConstraint("capacity_minutes >= 0", name="ck_work_schedule_day_capacity_non_negative"),
    )

    work_schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_schedules.id", ondelete="CASCADE"),
        nullable=False,
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    is_working_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    capacity_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return (
            f"<WorkScheduleDay id={self.id} weekday={self.weekday} "
            f"capacity_minutes={self.capacity_minutes}>"
        )
