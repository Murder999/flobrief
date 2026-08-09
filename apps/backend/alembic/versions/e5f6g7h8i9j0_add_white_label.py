"""add white label branding tables

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-07-08 17:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e5f6g7h8i9j0"
down_revision = "d4e5f6g7h8i9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agency_branding_settings",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_name_override", sa.String(255), nullable=True),
        sa.Column("primary_color", sa.String(7), nullable=True),
        sa.Column("secondary_color", sa.String(7), nullable=True),
        sa.Column("accent_color", sa.String(7), nullable=True),
        sa.Column("logo_asset_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "email_logo_asset_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "favicon_asset_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("custom_footer_text", sa.String(500), nullable=True),
        sa.Column("is_white_label_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["logo_asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["email_logo_asset_id"], ["assets.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["favicon_asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agency_id", name="uq_branding_agency_id"),
    )
    op.create_index("ix_branding_agency_id", "agency_branding_settings", ["agency_id"])

    op.create_table(
        "branding_assets",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_type", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ba_agency_id", "branding_assets", ["agency_id"])

    op.create_table(
        "custom_domain_settings",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("verification_token_hash", sa.String(64), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agency_id", name="uq_domain_agency_id"),
    )
    op.create_index("ix_cds_agency_id", "custom_domain_settings", ["agency_id"])


def downgrade() -> None:
    op.drop_index("ix_cds_agency_id", table_name="custom_domain_settings")
    op.drop_table("custom_domain_settings")
    op.drop_index("ix_ba_agency_id", table_name="branding_assets")
    op.drop_table("branding_assets")
    op.drop_index("ix_branding_agency_id", table_name="agency_branding_settings")
    op.drop_table("agency_branding_settings")
