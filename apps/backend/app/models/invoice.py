from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel
from app.models.enums import InvoiceStatus


class Invoice(BaseModel):
    """Billing invoice linked to a subscription."""

    __tablename__ = "invoices"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_invoice_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=InvoiceStatus.OPEN.value
    )
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hosted_invoice_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Invoice sub={self.subscription_id} "
            f"amount={self.amount_cents} status={self.status}>"
        )
