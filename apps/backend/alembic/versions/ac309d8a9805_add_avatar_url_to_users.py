"""add avatar_url to users

Revision ID: ac309d8a9805
Revises: v2w3x4y5z6a7
Create Date: 2026-07-14 14:27:17.436169

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "ac309d8a9805"
down_revision: Union[str, None] = "v2w3x4y5z6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
