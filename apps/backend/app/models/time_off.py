from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class TimeOff(BaseModel):
    """A leave request/period for a user. When `all_day=True`, `start_at`/
    `end_at` are stored as UTC midnight of the user's WorkSchedule timezone
    day boundaries — computed at write time in `TimeOffService` using
    `zoneinfo` — so a full-day leave never shifts by a day when viewed in a
    different timezone."""

    __tablename__ = "time_off"
    __table_args__ = (
        Index("ix_time_off_agency_id", "agency_id"),
        Index("ix_time_off_user_id", "user_id"),
        Index("ix_time_off_start_at", "start_at"),
        CheckConstraint("end_at >= start_at", name="ck_time_off_end_after_start"),
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
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="requested")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<TimeOff id={self.id} user_id={self.user_id} status={self.status}>"
