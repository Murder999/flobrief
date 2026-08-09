from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel
from app.models.enums import BillingEventStatus


class BillingEvent(BaseModel):
    """Immutable record of every incoming billing webhook event.

    Idempotency is enforced via the unique provider_event_id column.
    """

    __tablename__ = "billing_events"

    provider: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    provider_event_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BillingEventStatus.PENDING.value
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<BillingEvent provider={self.provider} "
            f"type={self.event_type} status={self.status}>"
        )
