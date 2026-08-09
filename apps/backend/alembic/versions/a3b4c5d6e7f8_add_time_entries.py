"""add time_entries table

Revision ID: a3b4c5d6e7f8
Revises: f1a2b3c4d5e6
Create Date: 2026-07-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a3b4c5d6e7f8"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "time_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deliverable_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("billable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source", sa.String(10), nullable=False, server_default="manual"),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("locked_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invoiced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rate_snapshot_cents", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["brief_id"], ["briefs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deliverable_id"], ["deliverables.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["brief_tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["locked_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at > started_at",
            name="ck_time_entry_end_after_start",
        ),
    )
    op.create_index("ix_time_entry_agency_id", "time_entries", ["agency_id"])
    op.create_index("ix_time_entry_user_id", "time_entries", ["user_id"])
    op.create_index("ix_time_entry_brief_id", "time_entries", ["brief_id"])
    op.create_index("ix_time_entry_brand_id", "time_entries", ["brand_id"])
    op.create_index("ix_time_entry_started_at", "time_entries", ["started_at"])
    op.create_index(
        "uq_time_entry_one_active_per_user",
        "time_entries",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_time_entry_one_active_per_user", table_name="time_entries")
    op.drop_index("ix_time_entry_started_at", table_name="time_entries")
    op.drop_index("ix_time_entry_brand_id", table_name="time_entries")
    op.drop_index("ix_time_entry_brief_id", table_name="time_entries")
    op.drop_index("ix_time_entry_user_id", table_name="time_entries")
    op.drop_index("ix_time_entry_agency_id", table_name="time_entries")
    op.drop_table("time_entries")
