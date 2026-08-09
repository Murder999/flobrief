"""add comments, threads, assets, asset versions and asset links

Revision ID: a1b2c3d4e5f6
Revises: f4a5b6c7d8e9
Create Date: 2026-07-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a1b2c3d4e5f6"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None

_UUID = postgresql.UUID(as_uuid=True)
_NOW = sa.text("now()")
_UUID_DEFAULT = sa.text("gen_random_uuid()")


def upgrade() -> None:
    # ── assets ────────────────────────────────────────────────────────────────
    op.create_table(
        "assets",
        sa.Column("id", _UUID, primary_key=True, server_default=_UUID_DEFAULT),
        sa.Column(
            "agency_id",
            _UUID,
            sa.ForeignKey("agencies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            _UUID,
            sa.ForeignKey("brands.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "uploaded_by_id",
            _UUID,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("filename", sa.String(300), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("storage_provider", sa.String(20), nullable=False, server_default="local"),
        sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_asset_agency_id", "assets", ["agency_id"])

    # ── asset_versions ────────────────────────────────────────────────────────
    op.create_table(
        "asset_versions",
        sa.Column("id", _UUID, primary_key=True, server_default=_UUID_DEFAULT),
        sa.Column(
            "asset_id",
            _UUID,
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("filename", sa.String(300), nullable=False),
        sa.Column("mime_type", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column(
            "uploaded_by_id",
            _UUID,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_av_asset_id", "asset_versions", ["asset_id"])

    # ── comment_threads ───────────────────────────────────────────────────────
    op.create_table(
        "comment_threads",
        sa.Column("id", _UUID, primary_key=True, server_default=_UUID_DEFAULT),
        sa.Column(
            "agency_id",
            _UUID,
            sa.ForeignKey("agencies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            _UUID,
            sa.ForeignKey("brands.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "brief_id",
            _UUID,
            sa.ForeignKey("briefs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "approval_id",
            _UUID,
            sa.ForeignKey("approvals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("field_key", sa.String(200), nullable=True),
        # asset_id stored without FK constraint to avoid circular dep
        sa.Column("asset_id", _UUID, nullable=True),
        sa.Column("thread_type", sa.String(20), nullable=False, server_default="brief"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column(
            "created_by_id",
            _UUID,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ct_agency_id", "comment_threads", ["agency_id"])
    op.create_index("ix_ct_brief_id", "comment_threads", ["brief_id"])

    # ── comments ──────────────────────────────────────────────────────────────
    op.create_table(
        "comments",
        sa.Column("id", _UUID, primary_key=True, server_default=_UUID_DEFAULT),
        sa.Column(
            "thread_id",
            _UUID,
            sa.ForeignKey("comment_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_user_id",
            _UUID,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("author_name", sa.String(255), nullable=True),
        sa.Column("author_email", sa.String(255), nullable=True),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="internal"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_comment_thread_id", "comments", ["thread_id"])

    # ── asset_links ───────────────────────────────────────────────────────────
    op.create_table(
        "asset_links",
        sa.Column("id", _UUID, primary_key=True, server_default=_UUID_DEFAULT),
        sa.Column(
            "asset_id",
            _UUID,
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brief_id",
            _UUID,
            sa.ForeignKey("briefs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        # calendar_item_id FK added in Part 9 when content_posts table exists
        sa.Column("calendar_item_id", _UUID, nullable=True),
        sa.Column(
            "comment_id",
            _UUID,
            sa.ForeignKey("comments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_al_asset_id", "asset_links", ["asset_id"])


def downgrade() -> None:
    op.drop_table("asset_links")
    op.drop_table("comments")
    op.drop_table("comment_threads")
    op.drop_table("asset_versions")
    op.drop_table("assets")
