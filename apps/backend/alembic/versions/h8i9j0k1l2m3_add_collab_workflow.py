"""add_collab_workflow

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "h8i9j0k1l2m3"
down_revision: Union[str, None] = "g7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add rejected_at to invitations
    op.add_column(
        "invitations",
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add participant columns to brief_assignees
    op.add_column(
        "brief_assignees",
        sa.Column("participant_role", sa.String(40), nullable=True),
    )
    op.add_column(
        "brief_assignees",
        sa.Column("can_comment", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "brief_assignees",
        sa.Column("can_upload", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "brief_assignees",
        sa.Column("can_edit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "brief_assignees",
        sa.Column("can_approve", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "brief_assignees",
        sa.Column(
            "can_request_revision", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )


def downgrade() -> None:
    op.drop_column("brief_assignees", "can_request_revision")
    op.drop_column("brief_assignees", "can_approve")
    op.drop_column("brief_assignees", "can_edit")
    op.drop_column("brief_assignees", "can_upload")
    op.drop_column("brief_assignees", "can_comment")
    op.drop_column("brief_assignees", "participant_role")
    op.drop_column("invitations", "rejected_at")
