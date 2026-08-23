"""add mentions and onboarding progress tables

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-07-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d1e2f3a4b5c6"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── mentions ─────────────────────────────────────────────────────────────
    op.create_table(
        "mentions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("mentioned_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mentioned_agency_member_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("mentioned_brand_member_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deliverable_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("display_text", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["mentioned_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["mentioned_agency_member_id"], ["agency_members.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["mentioned_brand_member_id"], ["brand_members.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brief_id"], ["briefs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deliverable_id"], ["deliverables.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mentions_agency_id", "mentions", ["agency_id"])
    op.create_index("ix_mentions_source", "mentions", ["source_type", "source_id"])
    op.create_index("ix_mentions_mentioned_user_id", "mentions", ["mentioned_user_id"])
    op.create_index("ix_mentions_brief_id", "mentions", ["brief_id"])
    # Partial unique index: only one *live* mention per (source, mentioned user).
    # A plain UniqueConstraint can't carry a WHERE clause, so this is expressed
    # directly as a Postgres partial index — it's what makes duplicate-mention
    # notification dedupe enforceable at the DB layer, not just in application code.
    op.create_index(
        "uq_mentions_source_user_live",
        "mentions",
        ["source_type", "source_id", "mentioned_user_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ── onboarding_progress ──────────────────────────────────────────────────
    op.create_table(
        "onboarding_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("onboarding_type", sa.String(30), nullable=False),
        sa.Column("current_step", sa.String(60), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("onboarding_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "onboarding_type", name="uq_onboarding_user_type"),
    )
    op.create_index("ix_onboarding_progress_user_id", "onboarding_progress", ["user_id"])
    op.create_index("ix_onboarding_progress_agency_id", "onboarding_progress", ["agency_id"])

    # ── onboarding_step_state ────────────────────────────────────────────────
    op.create_table(
        "onboarding_step_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("onboarding_progress_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_key", sa.String(60), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["onboarding_progress_id"], ["onboarding_progress.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "onboarding_progress_id", "step_key", name="uq_onboarding_step_progress_key"
        ),
    )
    op.create_index(
        "ix_onboarding_step_state_progress_id", "onboarding_step_state", ["onboarding_progress_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_onboarding_step_state_progress_id", table_name="onboarding_step_state")
    op.drop_table("onboarding_step_state")
    op.drop_index("ix_onboarding_progress_agency_id", table_name="onboarding_progress")
    op.drop_index("ix_onboarding_progress_user_id", table_name="onboarding_progress")
    op.drop_table("onboarding_progress")
    op.drop_index("uq_mentions_source_user_live", table_name="mentions")
    op.drop_index("ix_mentions_brief_id", table_name="mentions")
    op.drop_index("ix_mentions_mentioned_user_id", table_name="mentions")
    op.drop_index("ix_mentions_source", table_name="mentions")
    op.drop_index("ix_mentions_agency_id", table_name="mentions")
    op.drop_table("mentions")
