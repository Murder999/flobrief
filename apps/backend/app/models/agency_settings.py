from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class AgencySettings(BaseModel):
    """One row per agency (get-or-create on first access) holding capacity
    thresholds and finance defaults consumed by many future capacity/finance
    services. Plain typed columns, not a JSONB blob — matches how
    `Brand.timezone` is a typed column."""

    __tablename__ = "agency_settings"

    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    capacity_available_threshold_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60
    )
    capacity_balanced_threshold_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, default=85
    )
    capacity_near_threshold_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")
    default_payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    invoice_number_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retainer_default_rollover: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<AgencySettings id={self.id} agency_id={self.agency_id}>"
