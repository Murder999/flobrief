from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class PaymentCustomer(BaseModel):
    """Maps an agency (or brand) to a payment provider customer record."""

    __tablename__ = "payment_customers"

    agency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_customer_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    def __repr__(self) -> str:
        tenant = f"agency={self.agency_id}" if self.agency_id else f"brand={self.brand_id}"
        return f"<PaymentCustomer {tenant} provider={self.provider}>"
