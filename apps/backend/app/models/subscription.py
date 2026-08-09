import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel
from app.models.enums import BillingProvider, SubscriptionStatus


class Subscription(BaseModel):
    __tablename__ = "subscriptions"
    __table_args__ = (
        # Exactly one of agency_id or brand_id must be set — never both, never neither
        CheckConstraint(
            "(agency_id IS NOT NULL AND brand_id IS NULL)"
            " OR (agency_id IS NULL AND brand_id IS NOT NULL)",
            name="ck_subscription_exactly_one_tenant",
        ),
    )

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
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SubscriptionStatus.TRIALING.value
    )
    billing_provider: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BillingProvider.MANUAL.value
    )
    provider_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        tenant = f"agency={self.agency_id}" if self.agency_id else f"brand={self.brand_id}"
        return f"<Subscription {tenant} plan={self.plan_id} status={self.status}>"
