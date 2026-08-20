"""Add privacy-preserving public analytics events.

Revision ID: u6v7w8x9y0z1
Revises: t5u6v7w8x9y0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "u6v7w8x9y0z1"
down_revision: str | None = "t5u6v7w8x9y0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "public_analytics_events",
        sa.Column("session_hash", sa.String(length=64), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("medium", sa.String(length=100), nullable=False),
        sa.Column("referrer_host", sa.String(length=255), nullable=True),
        sa.Column("ai_provider", sa.String(length=50), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_public_analytics_events_created_at", "public_analytics_events", ["created_at"]
    )
    op.create_index(
        "ix_public_analytics_events_session_hash", "public_analytics_events", ["session_hash"]
    )
    op.create_index("ix_public_analytics_events_path", "public_analytics_events", ["path"])
    op.create_index(
        "ix_public_analytics_events_ai_provider", "public_analytics_events", ["ai_provider"]
    )


def downgrade() -> None:
    op.drop_table("public_analytics_events")
