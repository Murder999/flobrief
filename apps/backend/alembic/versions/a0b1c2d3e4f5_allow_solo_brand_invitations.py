"""Allow membership invitations for independent brand workspaces.

Revision ID: a0b1c2d3e4f5
Revises: z9a0b1c2d3e4
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a0b1c2d3e4f5"
down_revision: str | None = "z9a0b1c2d3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "invitations",
        "agency_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    op.execute("DELETE FROM invitations WHERE agency_id IS NULL")
    op.alter_column(
        "invitations",
        "agency_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
