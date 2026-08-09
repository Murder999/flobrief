"""add self-service demo sandboxes

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-07-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agencies",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "agencies",
        sa.Column("demo_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agencies",
        sa.Column("demo_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_agencies_demo_active",
        "agencies",
        ["is_demo", "demo_expires_at"],
    )

    op.create_table(
        "platform_demo_settings",
        sa.Column("setting_key", sa.String(50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("duration_hours", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("max_active_sandboxes", sa.Integer(), nullable=False, server_default="20"),
        sa.Column(
            "max_creations_per_ip_per_day",
            sa.Integer(),
            nullable=False,
            server_default="2",
        ),
        sa.Column("captcha_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("setting_key"),
    )
    op.create_index(
        "ix_platform_demo_setting_key",
        "platform_demo_settings",
        ["setting_key"],
        unique=True,
    )

    op.create_table(
        "demo_sandboxes",
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("termination_reason", sa.String(100), nullable=True),
        sa.Column("ip_hash", sa.String(64), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agency_id"),
    )
    op.create_index(
        "ix_demo_sandboxes_status_expires",
        "demo_sandboxes",
        ["status", "expires_at"],
    )
    op.create_index(
        "ix_demo_sandboxes_ip_created",
        "demo_sandboxes",
        ["ip_hash", "created_at"],
    )
    op.create_index(
        "ix_demo_sandboxes_agency_id",
        "demo_sandboxes",
        ["agency_id"],
        unique=True,
    )
    op.create_index(
        "ix_demo_sandboxes_owner_user_id",
        "demo_sandboxes",
        ["owner_user_id"],
    )
    op.create_index(
        "ix_demo_sandboxes_expires_at",
        "demo_sandboxes",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_table("demo_sandboxes")
    op.drop_table("platform_demo_settings")
    op.drop_index("ix_agencies_demo_active", table_name="agencies")
    op.drop_column("agencies", "demo_expires_at")
    op.drop_column("agencies", "demo_started_at")
    op.drop_column("agencies", "is_demo")
