"""add brief/brief_task estimate columns

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-07-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("briefs", sa.Column("estimated_hours", sa.Float(), nullable=True))
    op.add_column(
        "briefs",
        sa.Column("estimated_hours_by_category", postgresql.JSONB(), nullable=True),
    )
    op.add_column("brief_tasks", sa.Column("estimated_hours", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("brief_tasks", "estimated_hours")
    op.drop_column("briefs", "estimated_hours_by_category")
    op.drop_column("briefs", "estimated_hours")
