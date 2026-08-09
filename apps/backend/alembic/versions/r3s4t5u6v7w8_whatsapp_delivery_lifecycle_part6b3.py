"""whatsapp_delivery_lifecycle_part6b3

Part 6B-3 — delivery state machine timestamps, retry bookkeeping, template
version snapshots, and the indexes the retry worker / admin metrics need.

1. `notification_deliveries` gains per-transition timestamps not previously
   tracked (`accepted_at`, `cancelled_at`, `expired_at`), retry bookkeeping
   (`last_attempt_at`, `retry_exhausted_at` — `attempt_count`/`next_retry_at`
   already existed from Part 6A/6B-2), and a template-version snapshot
   (`template_revision`, `template_content_sid`) so a queued retry can detect
   a template that changed shape since the delivery was first created.
2. `notification_deliveries` gains a denormalized `agency_id` (nullable,
   SET NULL, backfilled from `notification_events.agency_id`) — the admin
   metrics/retry-claim queries need agency-scoped, status-scoped, time-scoped
   lookups that would otherwise require a JOIN on every call; this also
   removes the full-table-scan the Twilio webhook was doing on
   `provider_message_id` (now indexed) and speeds the same webhook's
   duplicate-callback handling.
3. `whatsapp_templates` gains `revision` (starts at 1, bumped by
   `WhatsAppTemplateRepository.update_approval` whenever `status` or
   `content_sid` actually changes) — the version snapshot in (1) is compared
   against this at send/retry time.

Revision ID: r3s4t5u6v7w8
Revises: q2r3s4t5u6v7
Create Date: 2026-07-29 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "r3s4t5u6v7w8"
down_revision: Union[str, None] = "q2r3s4t5u6v7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── notification_deliveries: state-machine + retry + template-snapshot columns ──
    op.add_column(
        "notification_deliveries", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "notification_deliveries", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "notification_deliveries", sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("retry_exhausted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_deliveries", sa.Column("template_revision", sa.Integer(), nullable=True)
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("template_content_sid", sa.String(length=100), nullable=True),
    )

    op.add_column(
        "notification_deliveries",
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        """
        UPDATE notification_deliveries
        SET agency_id = notification_events.agency_id
        FROM notification_events
        WHERE notification_deliveries.event_id = notification_events.id
          AND notification_deliveries.agency_id IS NULL
        """
    )
    op.create_foreign_key(
        "fk_ndel_agency_id",
        "notification_deliveries",
        "agencies",
        ["agency_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_ndel_provider_message_id",
        "notification_deliveries",
        ["provider_message_id"],
    )
    op.create_index(
        "ix_ndel_template_key",
        "notification_deliveries",
        ["template_key"],
    )
    op.create_index(
        "ix_ndel_retry_claim",
        "notification_deliveries",
        ["channel", "status", "next_retry_at"],
    )
    op.create_index(
        "ix_ndel_agency_status_created",
        "notification_deliveries",
        ["agency_id", "status", "created_at"],
    )

    # ── whatsapp_templates: revision counter ─────────────────────────────────
    op.add_column(
        "whatsapp_templates",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("whatsapp_templates", "revision", server_default=None)


def downgrade() -> None:
    op.drop_column("whatsapp_templates", "revision")

    op.drop_index("ix_ndel_agency_status_created", table_name="notification_deliveries")
    op.drop_index("ix_ndel_retry_claim", table_name="notification_deliveries")
    op.drop_index("ix_ndel_template_key", table_name="notification_deliveries")
    op.drop_index("ix_ndel_provider_message_id", table_name="notification_deliveries")

    op.drop_constraint("fk_ndel_agency_id", "notification_deliveries", type_="foreignkey")
    op.drop_column("notification_deliveries", "agency_id")

    op.drop_column("notification_deliveries", "template_content_sid")
    op.drop_column("notification_deliveries", "template_revision")
    op.drop_column("notification_deliveries", "retry_exhausted_at")
    op.drop_column("notification_deliveries", "last_attempt_at")
    op.drop_column("notification_deliveries", "expired_at")
    op.drop_column("notification_deliveries", "cancelled_at")
    op.drop_column("notification_deliveries", "accepted_at")
