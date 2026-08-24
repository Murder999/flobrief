"""Repair demo brand identity schema on previously migrated databases.

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "w8x9y0z1a2b3"
down_revision: str | None = "v7w8x9y0z1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("demo_sandboxes")}

    if "brand_user_id" not in columns:
        op.add_column(
            "demo_sandboxes",
            sa.Column("brand_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        )

    foreign_keys = {
        foreign_key["name"] for foreign_key in inspector.get_foreign_keys("demo_sandboxes")
    }
    if "fk_demo_sandboxes_brand_user_id_users" not in foreign_keys:
        op.create_foreign_key(
            "fk_demo_sandboxes_brand_user_id_users",
            "demo_sandboxes",
            "users",
            ["brand_user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    indexes = {index["name"] for index in inspector.get_indexes("demo_sandboxes")}
    if "ix_demo_sandboxes_brand_user_id" not in indexes:
        op.create_index("ix_demo_sandboxes_brand_user_id", "demo_sandboxes", ["brand_user_id"])


def downgrade() -> None:
    # The preceding t5 revision already declares this schema. Downgrading this
    # repair must preserve the schema expected at v7 rather than remove it.
    pass
