"""add content calendar

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-08 12:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6g7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── calendar_items ────────────────────────────────────────────────────────
    op.create_table(
        "calendar_items",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agency_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("brief_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("briefs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("item_type", sa.String(30), nullable=False, server_default="post"),
        sa.Column("platform", sa.String(30), nullable=False, server_default="other"),
        sa.Column("status", sa.String(30), nullable=False, server_default="planned"),
        sa.Column("publish_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("color_label", sa.String(30), nullable=True),
        sa.Column("created_by_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_cal_agency_id", "calendar_items", ["agency_id"])
    op.create_index("ix_cal_brand_id", "calendar_items", ["brand_id"])
    op.create_index("ix_cal_publish_at", "calendar_items", ["publish_at"])
    op.create_index("ix_cal_status", "calendar_items", ["status"])

    # ── calendar_item_assets ──────────────────────────────────────────────────
    op.create_table(
        "calendar_item_assets",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("calendar_item_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("calendar_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_cia_calendar_item_id", "calendar_item_assets", ["calendar_item_id"])

    # ── calendar_item_assignees ───────────────────────────────────────────────
    op.create_table(
        "calendar_item_assignees",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("calendar_item_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("calendar_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ciasgn_calendar_item_id", "calendar_item_assignees", ["calendar_item_id"])

    # ── calendar_item_status_history ──────────────────────────────────────────
    op.create_table(
        "calendar_item_status_history",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("calendar_item_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("calendar_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("old_status", sa.String(30), nullable=True),
        sa.Column("new_status", sa.String(30), nullable=False),
        sa.Column("changed_by_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_cish_calendar_item_id", "calendar_item_status_history", ["calendar_item_id"])

    # ── Add FK on asset_links.calendar_item_id (deferred from Part 8) ─────────
    op.create_index("ix_al_calendar_item_id", "asset_links", ["calendar_item_id"])
    op.create_foreign_key(
        "fk_asset_links_calendar_item_id",
        "asset_links",
        "calendar_items",
        ["calendar_item_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_asset_links_calendar_item_id", "asset_links", type_="foreignkey")
    op.drop_index("ix_al_calendar_item_id", table_name="asset_links")

    op.drop_index("ix_cish_calendar_item_id", table_name="calendar_item_status_history")
    op.drop_table("calendar_item_status_history")

    op.drop_index("ix_ciasgn_calendar_item_id", table_name="calendar_item_assignees")
    op.drop_table("calendar_item_assignees")

    op.drop_index("ix_cia_calendar_item_id", table_name="calendar_item_assets")
    op.drop_table("calendar_item_assets")

    op.drop_index("ix_cal_status", table_name="calendar_items")
    op.drop_index("ix_cal_publish_at", table_name="calendar_items")
    op.drop_index("ix_cal_brand_id", table_name="calendar_items")
    op.drop_index("ix_cal_agency_id", table_name="calendar_items")
    op.drop_table("calendar_items")
