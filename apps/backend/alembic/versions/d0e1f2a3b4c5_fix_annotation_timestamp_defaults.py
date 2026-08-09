"""fix deliverable_annotations/annotation_replies missing timestamp defaults

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-07-16

The original migration (v2w3x4y5z6a7) created created_at/updated_at as
nullable, with no server_default — mismatched against the SQLAlchemy model
(BaseModel/TimestampMixin), which declares nullable=False,
server_default=func.now(). Confirmed live: a real INSERT left both columns
NULL, which then crashed AnnotationRead/BrandAnnotationRead response
serialization (created_at is a required datetime field). This backfills any
existing NULLs then aligns the DB constraint with the model.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None

_TABLES = ("deliverable_annotations", "annotation_replies")


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"UPDATE {table} SET created_at = now() WHERE created_at IS NULL")
        op.execute(f"UPDATE {table} SET updated_at = now() WHERE updated_at IS NULL")
        op.alter_column(
            table,
            "created_at",
            nullable=False,
            server_default=sa.text("now()"),
        )
        op.alter_column(
            table,
            "updated_at",
            nullable=False,
            server_default=sa.text("now()"),
        )


def downgrade() -> None:
    for table in _TABLES:
        op.alter_column(table, "created_at", nullable=True, server_default=None)
        op.alter_column(table, "updated_at", nullable=True, server_default=None)
