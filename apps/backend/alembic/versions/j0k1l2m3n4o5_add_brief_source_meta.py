"""add_brief_source_meta

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-07-10 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "j0k1l2m3n4o5"
down_revision: Union[str, None] = "i9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "briefs",
        sa.Column("source", sa.String(30), nullable=True, server_default="agency"),
    )
    op.add_column(
        "briefs",
        sa.Column("meta", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_brief_source", "briefs", ["source"])


def downgrade() -> None:
    op.drop_index("ix_brief_source", table_name="briefs")
    op.drop_column("briefs", "meta")
    op.drop_column("briefs", "source")
