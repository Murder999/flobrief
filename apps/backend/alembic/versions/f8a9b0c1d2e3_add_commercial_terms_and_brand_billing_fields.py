"""add commercial terms and brand billing fields

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-07-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── commercial_terms ─────────────────────────────────────────────────────
    op.create_table(
        "commercial_terms",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("billing_model", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="TRY"),
        sa.Column("hourly_rate_cents", sa.Integer(), nullable=True),
        sa.Column("fixed_fee_cents", sa.Integer(), nullable=True),
        sa.Column("retainer_amount_cents", sa.Integer(), nullable=True),
        sa.Column("retainer_included_minutes", sa.Integer(), nullable=True),
        sa.Column("overage_rate_cents", sa.Integer(), nullable=True),
        sa.Column("per_item_rate_cents", sa.Integer(), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("tax_rate_bps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discount_rate_bps", sa.Integer(), nullable=True),
        sa.Column("billing_contact_name", sa.String(255), nullable=True),
        sa.Column("billing_contact_email", sa.String(255), nullable=True),
        sa.Column("billing_address", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tax_office", sa.String(255), nullable=True),
        sa.Column("tax_number", sa.String(50), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "tax_rate_bps >= 0 AND tax_rate_bps <= 10000",
            name="ck_commercial_terms_tax_rate_range",
        ),
        sa.CheckConstraint(
            "discount_rate_bps IS NULL OR (discount_rate_bps >= 0 AND discount_rate_bps <= 10000)",
            name="ck_commercial_terms_discount_rate_range",
        ),
        sa.CheckConstraint(
            "hourly_rate_cents IS NULL OR hourly_rate_cents >= 0",
            name="ck_commercial_terms_hourly_rate_non_negative",
        ),
        sa.CheckConstraint(
            "fixed_fee_cents IS NULL OR fixed_fee_cents >= 0",
            name="ck_commercial_terms_fixed_fee_non_negative",
        ),
        sa.CheckConstraint(
            "retainer_amount_cents IS NULL OR retainer_amount_cents >= 0",
            name="ck_commercial_terms_retainer_amount_non_negative",
        ),
        sa.CheckConstraint(
            "retainer_included_minutes IS NULL OR retainer_included_minutes >= 0",
            name="ck_commercial_terms_retainer_minutes_non_negative",
        ),
        sa.CheckConstraint(
            "overage_rate_cents IS NULL OR overage_rate_cents >= 0",
            name="ck_commercial_terms_overage_rate_non_negative",
        ),
        sa.CheckConstraint(
            "per_item_rate_cents IS NULL OR per_item_rate_cents >= 0",
            name="ck_commercial_terms_per_item_rate_non_negative",
        ),
        sa.CheckConstraint(
            "payment_terms_days >= 0", name="ck_commercial_terms_payment_terms_non_negative"
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until >= valid_from",
            name="ck_commercial_terms_valid_until_after_from",
        ),
    )
    op.create_index("ix_commercial_terms_agency_id", "commercial_terms", ["agency_id"])
    op.create_index("ix_commercial_terms_brand_id", "commercial_terms", ["brand_id"])
    op.create_index(
        "uq_commercial_terms_one_active_per_brand",
        "commercial_terms",
        ["agency_id", "brand_id"],
        unique=True,
        postgresql_where=sa.text("active AND deleted_at IS NULL"),
    )

    # ── member_cost_rates ─────────────────────────────────────────────────────
    op.create_table(
        "member_cost_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("role", sa.String(30), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="TRY"),
        sa.Column("hourly_cost_cents", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(user_id IS NOT NULL AND role IS NULL) OR (user_id IS NULL AND role IS NOT NULL)",
            name="ck_member_cost_rate_exactly_one_target",
        ),
        sa.CheckConstraint("hourly_cost_cents > 0", name="ck_member_cost_rate_cost_positive"),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until >= valid_from",
            name="ck_member_cost_rate_valid_until_after_from",
        ),
    )
    op.create_index("ix_member_cost_rate_agency_id", "member_cost_rates", ["agency_id"])
    op.create_index("ix_member_cost_rate_user_id", "member_cost_rates", ["user_id"])
    op.create_index(
        "uq_member_cost_rate_one_open_ended_per_user",
        "member_cost_rates",
        ["agency_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("valid_until IS NULL AND active AND deleted_at IS NULL"),
    )
    op.create_index(
        "uq_member_cost_rate_one_open_ended_per_role",
        "member_cost_rates",
        ["agency_id", "role"],
        unique=True,
        postgresql_where=sa.text("valid_until IS NULL AND active AND deleted_at IS NULL"),
    )

    # ── Brand additive billing columns ──────────────────────────────────────
    op.add_column(
        "brands",
        sa.Column("currency", sa.String(3), nullable=False, server_default="TRY"),
    )
    op.add_column(
        "brands",
        sa.Column("billing_address", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("brands", sa.Column("tax_office", sa.String(255), nullable=True))
    op.add_column("brands", sa.Column("tax_number", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("brands", "tax_number")
    op.drop_column("brands", "tax_office")
    op.drop_column("brands", "billing_address")
    op.drop_column("brands", "currency")

    op.drop_index("uq_member_cost_rate_one_open_ended_per_role", table_name="member_cost_rates")
    op.drop_index("uq_member_cost_rate_one_open_ended_per_user", table_name="member_cost_rates")
    op.drop_index("ix_member_cost_rate_user_id", table_name="member_cost_rates")
    op.drop_index("ix_member_cost_rate_agency_id", table_name="member_cost_rates")
    op.drop_table("member_cost_rates")

    op.drop_index("uq_commercial_terms_one_active_per_brand", table_name="commercial_terms")
    op.drop_index("ix_commercial_terms_brand_id", table_name="commercial_terms")
    op.drop_index("ix_commercial_terms_agency_id", table_name="commercial_terms")
    op.drop_table("commercial_terms")
