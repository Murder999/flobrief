"""add calendar_items.milestone_type

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("calendar_items", sa.Column("milestone_type", sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column("calendar_items", "milestone_type")
