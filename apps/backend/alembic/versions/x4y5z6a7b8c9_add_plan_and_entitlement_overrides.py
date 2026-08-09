"""add plan brand/invite limits and entitlement_overrides table

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-07-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "x4y5z6a7b8c9"
down_revision = "w3x4y5z6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("max_brand_users", sa.Integer(), nullable=True))
    op.add_column(
        "plans", sa.Column("max_pending_agency_invites", sa.Integer(), nullable=True)
    )
    op.add_column(
        "plans", sa.Column("max_pending_brand_invites", sa.Integer(), nullable=True)
    )

    op.create_table(
        "entitlement_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("limit_key", sa.String(50), nullable=False),
        sa.Column("limit_value", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(agency_id IS NOT NULL AND brand_id IS NULL)"
            " OR (agency_id IS NULL AND brand_id IS NOT NULL)",
            name="ck_entitlement_override_exactly_one_tenant",
        ),
        sa.UniqueConstraint(
            "agency_id", "brand_id", "limit_key", name="uq_entitlement_override_tenant_key"
        ),
    )
    op.create_index("ix_eo_agency_id", "entitlement_overrides", ["agency_id"])
    op.create_index("ix_eo_brand_id", "entitlement_overrides", ["brand_id"])


def downgrade() -> None:
    op.drop_index("ix_eo_brand_id", table_name="entitlement_overrides")
    op.drop_index("ix_eo_agency_id", table_name="entitlement_overrides")
    op.drop_table("entitlement_overrides")
    op.drop_column("plans", "max_pending_brand_invites")
    op.drop_column("plans", "max_pending_agency_invites")
    op.drop_column("plans", "max_brand_users")
