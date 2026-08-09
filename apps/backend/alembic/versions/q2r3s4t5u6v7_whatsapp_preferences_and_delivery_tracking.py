"""whatsapp_preferences_and_delivery_tracking

Part 6B-2 — per-event WhatsApp preferences, consent provenance, and delivery
recipient tracking.

1. `users` gains `whatsapp_consent_source` / `whatsapp_consent_version` —
   additive provenance for the existing `whatsapp_opt_in*` columns (Part 6A).
   Nothing reads these as authoritative until the consent endpoint sets them;
   existing opted-in rows simply have NULL provenance, which the API surfaces
   honestly rather than backfilling a guess.
2. New table `notification_event_preferences` — one row per (user, event_type)
   holding the per-event WhatsApp toggle, with a DB-level unique constraint so
   two concurrent writes can never create duplicate rows for the same event.
   Absence of a row means "not yet customized" (falls back to the master
   `notification_preferences.whatsapp_enabled` toggle) — never backfilled here.
3. `notification_deliveries` gains `recipient_user_id` — the existing table had
   no durable link from a delivery row back to which user actually received
   it (only `recipient_email` / `recipient_phone_masked`), which the Owner
   delivery-history view needs to show a display name. Nullable/SET NULL so
   existing rows and non-recipient-specific deliveries are unaffected.

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-07-28 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "q2r3s4t5u6v7"
down_revision: Union[str, None] = "p1q2r3s4t5u6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("whatsapp_consent_source", sa.String(length=30), nullable=True)
    )
    op.add_column(
        "users", sa.Column("whatsapp_consent_version", sa.String(length=20), nullable=True)
    )

    op.create_table(
        "notification_event_preferences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
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
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("whatsapp_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_nevpref_user_id",
        "notification_event_preferences",
        ["user_id"],
    )
    op.create_unique_constraint(
        "uq_nevpref_user_event",
        "notification_event_preferences",
        ["user_id", "event_type"],
    )

    op.add_column(
        "notification_deliveries",
        sa.Column("recipient_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_ndel_recipient_user_id",
        "notification_deliveries",
        ["recipient_user_id"],
    )
    op.create_foreign_key(
        "fk_ndel_recipient_user_id",
        "notification_deliveries",
        "users",
        ["recipient_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_ndel_recipient_user_id", "notification_deliveries", type_="foreignkey"
    )
    op.drop_index("ix_ndel_recipient_user_id", table_name="notification_deliveries")
    op.drop_column("notification_deliveries", "recipient_user_id")

    op.drop_constraint(
        "uq_nevpref_user_event", "notification_event_preferences", type_="unique"
    )
    op.drop_index("ix_nevpref_user_id", table_name="notification_event_preferences")
    op.drop_table("notification_event_preferences")

    op.drop_column("users", "whatsapp_consent_version")
    op.drop_column("users", "whatsapp_consent_source")
