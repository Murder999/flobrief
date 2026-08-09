"""add_seo_fields_to_branding

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-07-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, None] = "h8i9j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agency_branding_settings",
        sa.Column("seo_title", sa.String(60), nullable=True),
    )
    op.add_column(
        "agency_branding_settings",
        sa.Column("seo_description", sa.String(160), nullable=True),
    )
    op.add_column(
        "agency_branding_settings",
        sa.Column("og_image_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "agency_branding_settings",
        sa.Column("google_analytics_id", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agency_branding_settings", "google_analytics_id")
    op.drop_column("agency_branding_settings", "og_image_url")
    op.drop_column("agency_branding_settings", "seo_description")
    op.drop_column("agency_branding_settings", "seo_title")
