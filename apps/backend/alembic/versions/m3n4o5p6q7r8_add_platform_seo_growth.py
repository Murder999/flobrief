"""add_platform_seo_growth

Adds:
- platform_seo_page_settings table
- platform_growth_settings table

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-07-11 10:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "m3n4o5p6q7r8"
down_revision: Union[str, None] = "l2m3n4o5p6q7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── platform_seo_page_settings ────────────────────────────────────────────
    op.create_table(
        "platform_seo_page_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("page_key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("canonical_url", sa.String(500), nullable=True),
        sa.Column("og_title", sa.String(200), nullable=True),
        sa.Column("og_description", sa.String(500), nullable=True),
        sa.Column("og_image_url", sa.String(500), nullable=True),
        sa.Column("twitter_title", sa.String(200), nullable=True),
        sa.Column("twitter_description", sa.String(500), nullable=True),
        sa.Column("indexable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("follow_links", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("page_key", name="uq_seo_page_key"),
    )
    op.create_index("ix_seo_page_key", "platform_seo_page_settings", ["page_key"], unique=True)

    # ── platform_growth_settings ──────────────────────────────────────────────
    op.create_table(
        "platform_growth_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("setting_key", sa.String(50), nullable=False, server_default="default"),
        sa.Column("google_analytics_id", sa.String(100), nullable=True),
        sa.Column("google_tag_manager_id", sa.String(100), nullable=True),
        sa.Column("search_console_verification", sa.String(200), nullable=True),
        sa.Column("meta_pixel_id", sa.String(100), nullable=True),
        sa.Column("linkedin_partner_id", sa.String(100), nullable=True),
        sa.Column("robots_txt", sa.Text(), nullable=True),
        sa.Column("sitemap_last_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_app_url", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("setting_key", name="uq_growth_setting_key"),
    )
    op.create_index(
        "ix_growth_setting_key", "platform_growth_settings", ["setting_key"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_growth_setting_key", table_name="platform_growth_settings")
    op.drop_table("platform_growth_settings")
    op.drop_index("ix_seo_page_key", table_name="platform_seo_page_settings")
    op.drop_table("platform_seo_page_settings")
