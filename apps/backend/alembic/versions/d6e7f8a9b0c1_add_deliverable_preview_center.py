"""add deliverable preview center tables

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-07-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deliverable_preview_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deliverable_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("preview_format", sa.String(30), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("cta_label", sa.String(80), nullable=True),
        sa.Column("hashtags", postgresql.JSONB(), nullable=True),
        sa.Column("display_name_override", sa.String(255), nullable=True),
        sa.Column("profile_photo_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cover_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["brief_id"], ["briefs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deliverable_id"], ["deliverables.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["profile_photo_asset_id"], ["assets.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["cover_asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deliverable_id", name="uq_dpc_deliverable_id"),
    )
    op.create_index(
        "ix_dpc_deliverable_id", "deliverable_preview_configs", ["deliverable_id"]
    )
    op.create_index("ix_dpc_agency_id", "deliverable_preview_configs", ["agency_id"])

    op.create_table(
        "deliverable_preview_slots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deliverable_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_cover", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["deliverable_id"], ["deliverables.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "deliverable_id", "asset_id", name="uq_dps_deliverable_asset"
        ),
    )
    op.create_index("ix_dps_deliverable_id", "deliverable_preview_slots", ["deliverable_id"])


def downgrade() -> None:
    op.drop_index("ix_dps_deliverable_id", table_name="deliverable_preview_slots")
    op.drop_table("deliverable_preview_slots")
    op.drop_index("ix_dpc_agency_id", table_name="deliverable_preview_configs")
    op.drop_index("ix_dpc_deliverable_id", table_name="deliverable_preview_configs")
    op.drop_table("deliverable_preview_configs")
