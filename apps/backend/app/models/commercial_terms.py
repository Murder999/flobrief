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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class CommercialTerms(BaseModel):
    """The billing arrangement between an agency and one of its brand
    clients — hourly/fixed-fee/retainer/per-item/hybrid, currency, rates, tax
    and discount basis points, and billing/tax identity used on invoices.
    Historical rows are kept (never deleted on change): `active=True` marks
    the single currently-effective row per brand, enforced by a partial
    unique index. Superseding an active row transactionally closes the prior
    one's `active`/`valid_until` in `CommercialTermsService` — never an
    in-place rewrite of terms that may already be reflected on issued
    invoices."""

    __tablename__ = "commercial_terms"
    __table_args__ = (
        Index("ix_commercial_terms_agency_id", "agency_id"),
        Index("ix_commercial_terms_brand_id", "brand_id"),
        Index(
            "uq_commercial_terms_one_active_per_brand",
            "agency_id",
            "brand_id",
            unique=True,
            postgresql_where=text("active AND deleted_at IS NULL"),
        ),
        CheckConstraint(
            "tax_rate_bps >= 0 AND tax_rate_bps <= 10000",
            name="ck_commercial_terms_tax_rate_range",
        ),
        CheckConstraint(
            "discount_rate_bps IS NULL OR (discount_rate_bps >= 0 AND discount_rate_bps <= 10000)",
            name="ck_commercial_terms_discount_rate_range",
        ),
        CheckConstraint(
            "hourly_rate_cents IS NULL OR hourly_rate_cents >= 0",
            name="ck_commercial_terms_hourly_rate_non_negative",
        ),
        CheckConstraint(
            "fixed_fee_cents IS NULL OR fixed_fee_cents >= 0",
            name="ck_commercial_terms_fixed_fee_non_negative",
        ),
        CheckConstraint(
            "retainer_amount_cents IS NULL OR retainer_amount_cents >= 0",
            name="ck_commercial_terms_retainer_amount_non_negative",
        ),
        CheckConstraint(
            "retainer_included_minutes IS NULL OR retainer_included_minutes >= 0",
            name="ck_commercial_terms_retainer_minutes_non_negative",
        ),
        CheckConstraint(
            "overage_rate_cents IS NULL OR overage_rate_cents >= 0",
            name="ck_commercial_terms_overage_rate_non_negative",
        ),
        CheckConstraint(
            "per_item_rate_cents IS NULL OR per_item_rate_cents >= 0",
            name="ck_commercial_terms_per_item_rate_non_negative",
        ),
        CheckConstraint(
            "payment_terms_days >= 0", name="ck_commercial_terms_payment_terms_non_negative"
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until >= valid_from",
            name="ck_commercial_terms_valid_until_after_from",
        ),
    )

    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    billing_model: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")
    hourly_rate_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fixed_fee_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retainer_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retainer_included_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overage_rate_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    per_item_rate_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    tax_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discount_rate_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    billing_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    billing_contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    billing_address: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tax_office: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<CommercialTerms id={self.id} brand_id={self.brand_id} "
            f"billing_model={self.billing_model} active={self.active}>"
        )


class MemberCostRate(BaseModel):
    """Internal hourly cost of a team member's time, used only for
    profitability math — never surfaced to a `COST_RATE_VIEW`-lacking role
    (Designer/Developer/Social Media Manager/Viewer/Brand-portal users, and
    even Admin by default per plan §8). Exactly one of `user_id`/`role` is
    set (a per-user override or a per-role fallback rate). Superseding an
    open-ended (`valid_until IS NULL`) active rate closes the prior row
    transactionally in `MemberCostRateService` — history is preserved for
    already-invoiced-time rate-snapshot stability."""

    __tablename__ = "member_cost_rates"
    __table_args__ = (
        Index("ix_member_cost_rate_agency_id", "agency_id"),
        Index("ix_member_cost_rate_user_id", "user_id"),
        Index(
            "uq_member_cost_rate_one_open_ended_per_user",
            "agency_id",
            "user_id",
            unique=True,
            postgresql_where=text("valid_until IS NULL AND active AND deleted_at IS NULL"),
        ),
        Index(
            "uq_member_cost_rate_one_open_ended_per_role",
            "agency_id",
            "role",
            unique=True,
            postgresql_where=text("valid_until IS NULL AND active AND deleted_at IS NULL"),
        ),
        CheckConstraint(
            "(user_id IS NOT NULL AND role IS NULL) OR (user_id IS NULL AND role IS NOT NULL)",
            name="ck_member_cost_rate_exactly_one_target",
        ),
        CheckConstraint("hourly_cost_cents > 0", name="ck_member_cost_rate_cost_positive"),
        CheckConstraint(
            "valid_until IS NULL OR valid_until >= valid_from",
            name="ck_member_cost_rate_valid_until_after_from",
        ),
    )

    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    role: Mapped[str | None] = mapped_column(String(30), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")
    hourly_cost_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        target = f"user_id={self.user_id}" if self.user_id else f"role={self.role}"
        return f"<MemberCostRate id={self.id} {target} active={self.active}>"
