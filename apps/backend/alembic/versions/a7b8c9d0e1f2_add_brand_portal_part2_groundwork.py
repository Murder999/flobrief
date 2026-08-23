"""brand portal part 2 groundwork: calendar priority, brand identity suggestions,
notification category matrix, extended brand profile fields

Revision ID: a7b8c9d0e1f2
Revises: z6a7b8c9d0e1
Create Date: 2026-07-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a7b8c9d0e1f2"
down_revision = "z6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "calendar_items",
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
    )

    op.add_column(
        "notification_preferences",
        sa.Column(
            "category_preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )

    op.add_column("brands", sa.Column("industry", sa.String(100), nullable=True))
    op.add_column("brands", sa.Column("website", sa.String(500), nullable=True))
    op.add_column("brands", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("brands", sa.Column("contact_email", sa.String(255), nullable=True))
    op.add_column("brands", sa.Column("contact_phone", sa.String(50), nullable=True))
    op.add_column(
        "brands",
        sa.Column("social_links", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "brands",
        sa.Column("default_language", sa.String(10), nullable=False, server_default="tr"),
    )
    op.add_column(
        "brands",
        sa.Column("timezone", sa.String(50), nullable=False, server_default="Europe/Istanbul"),
    )

    op.create_table(
        "brand_identity_suggestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brand_identity_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "proposed_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "proposed_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("applied_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "resolved_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_bis_profile_id", "brand_identity_suggestions", ["profile_id"])
    op.create_index("ix_bis_status", "brand_identity_suggestions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_bis_status", table_name="brand_identity_suggestions")
    op.drop_index("ix_bis_profile_id", table_name="brand_identity_suggestions")
    op.drop_table("brand_identity_suggestions")

    op.drop_column("brands", "timezone")
    op.drop_column("brands", "default_language")
    op.drop_column("brands", "social_links")
    op.drop_column("brands", "contact_phone")
    op.drop_column("brands", "contact_email")
    op.drop_column("brands", "description")
    op.drop_column("brands", "website")
    op.drop_column("brands", "industry")

    op.drop_column("notification_preferences", "category_preferences")

    op.drop_column("calendar_items", "priority")
