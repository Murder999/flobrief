from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class CapacityException(BaseModel):
    """An ad-hoc, one-off override of a user's capacity for a single date —
    e.g. a reduced-hours day, an extra-capacity crunch day, or an office
    closure. Replaces (not adds to) the WorkScheduleDay figure for that date."""

    __tablename__ = "capacity_exceptions"
    __table_args__ = (
        Index("ix_capacity_exception_agency_id", "agency_id"),
        Index("ix_capacity_exception_user_id", "user_id"),
        Index(
            "uq_capacity_exception_user_date",
            "user_id",
            "date",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint(
            "capacity_minutes >= 0", name="ck_capacity_exception_capacity_non_negative"
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
    date: Mapped[date] = mapped_column(Date, nullable=False)
    capacity_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    exception_type: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<CapacityException id={self.id} user_id={self.user_id} date={self.date}>"
