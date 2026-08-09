"""add brief planning fields (typed platforms/content_types, extra dates)

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-07-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "w3x4y5z6a7b8"
down_revision = "ac309d8a9805"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("briefs", sa.Column("platforms", postgresql.JSONB(), nullable=True))
    op.add_column("briefs", sa.Column("content_types", postgresql.JSONB(), nullable=True))
    op.add_column("briefs", sa.Column("start_date", sa.String(10), nullable=True))
    op.add_column("briefs", sa.Column("draft_date", sa.String(10), nullable=True))
    op.add_column("briefs", sa.Column("feedback_date", sa.String(10), nullable=True))
    op.add_column("briefs", sa.Column("publish_date", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("briefs", "publish_date")
    op.drop_column("briefs", "feedback_date")
    op.drop_column("briefs", "draft_date")
    op.drop_column("briefs", "start_date")
    op.drop_column("briefs", "content_types")
    op.drop_column("briefs", "platforms")
