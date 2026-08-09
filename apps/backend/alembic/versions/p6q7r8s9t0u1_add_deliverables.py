"""add deliverables table + asset visibility + asset_links deliverable_id

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-07-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "p6q7r8s9t0u1"
down_revision = "o5p6q7r8s9t0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deliverables",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("description_html", sa.Text(), nullable=True),
        sa.Column("deliverable_type", sa.String(30), nullable=False, server_default="other"),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("revision_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revision_note", sa.Text(), nullable=True),
        sa.Column("approve_note", sa.Text(), nullable=True),
        sa.Column("submitted_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["brief_id"], ["briefs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submitted_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deliverable_brief_id", "deliverables", ["brief_id"])
    op.create_index("ix_deliverable_agency_id", "deliverables", ["agency_id"])

    op.add_column(
        "assets",
        sa.Column("visibility", sa.String(20), nullable=False, server_default="internal"),
    )

    op.add_column(
        "asset_links",
        sa.Column("deliverable_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_asset_links_deliverable_id",
        "asset_links",
        "deliverables",
        ["deliverable_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_asset_links_deliverable_id", "asset_links", type_="foreignkey")
    op.drop_column("asset_links", "deliverable_id")
    op.drop_column("assets", "visibility")
    op.drop_index("ix_deliverable_agency_id", table_name="deliverables")
    op.drop_index("ix_deliverable_brief_id", table_name="deliverables")
    op.drop_table("deliverables")
