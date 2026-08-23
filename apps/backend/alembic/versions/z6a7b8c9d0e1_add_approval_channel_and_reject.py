"""add approval channel, decided_by, assigned_to for brand-portal decisions

Revision ID: z6a7b8c9d0e1
Revises: y5z6a7b8c9d0
Create Date: 2026-07-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "z6a7b8c9d0e1"
down_revision = "y5z6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "approvals",
        sa.Column("channel", sa.String(20), nullable=False, server_default="public_token"),
    )
    op.add_column(
        "approvals",
        sa.Column("decided_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "approvals",
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_approval_decided_by_user_id",
        "approvals",
        "users",
        ["decided_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_approval_assigned_to_user_id",
        "approvals",
        "users",
        ["assigned_to_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_approval_assigned_to_user_id", "approvals", type_="foreignkey")
    op.drop_constraint("fk_approval_decided_by_user_id", "approvals", type_="foreignkey")
    op.drop_column("approvals", "assigned_to_user_id")
    op.drop_column("approvals", "decided_by_user_id")
    op.drop_column("approvals", "channel")
