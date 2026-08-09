"""add_platform_branding_defaults

Adds platform_branding_defaults singleton table: global white-label
identity used as a fallback for agencies without their own branding.

Revision ID: f1a2b3c4d5e6
Revises: d0e1f2a3b4c5
Create Date: 2026-07-17 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_branding_defaults",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("setting_key", sa.String(50), nullable=False, server_default="default"),
        sa.Column("portal_name", sa.String(120), nullable=True),
        sa.Column("login_title", sa.String(200), nullable=True),
        sa.Column("login_description", sa.String(500), nullable=True),
        sa.Column("primary_color", sa.String(7), nullable=True),
        sa.Column("accent_color", sa.String(7), nullable=True),
        sa.Column("background_color", sa.String(7), nullable=True),
        sa.Column("surface_color", sa.String(7), nullable=True),
        sa.Column("text_color", sa.String(7), nullable=True),
        sa.Column("link_color", sa.String(7), nullable=True),
        sa.Column("logo_storage_key", sa.String(500), nullable=True),
        sa.Column("logo_mime_type", sa.String(127), nullable=True),
        sa.Column("logo_dark_storage_key", sa.String(500), nullable=True),
        sa.Column("logo_dark_mime_type", sa.String(127), nullable=True),
        sa.Column("favicon_storage_key", sa.String(500), nullable=True),
        sa.Column("favicon_mime_type", sa.String(127), nullable=True),
        sa.Column("email_from_name", sa.String(200), nullable=True),
        sa.Column("support_email", sa.String(255), nullable=True),
        sa.Column("footer_text", sa.String(500), nullable=True),
        sa.Column("terms_url", sa.String(500), nullable=True),
        sa.Column("privacy_url", sa.String(500), nullable=True),
        sa.Column("social_links", JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("setting_key", name="uq_platform_branding_setting_key"),
    )
    op.create_index(
        "ix_platform_branding_setting_key",
        "platform_branding_defaults",
        ["setting_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_platform_branding_setting_key", table_name="platform_branding_defaults")
    op.drop_table("platform_branding_defaults")
