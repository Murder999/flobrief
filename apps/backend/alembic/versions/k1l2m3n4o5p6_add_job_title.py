"""add_job_title

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-07-10 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k1l2m3n4o5p6"
down_revision: Union[str, None] = "j0k1l2m3n4o5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("job_title", sa.String(200), nullable=True))
    op.add_column("comments", sa.Column("author_job_title", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("comments", "author_job_title")
    op.drop_column("users", "job_title")
