"""whatsapp_template_registry

Part 6A — WhatsApp real-provider completion + controlled test send.

Adds:
- whatsapp_templates: event_type, provider, content_sid, status, variable_schema,
  updated_by_id, approved_at; drops unused is_active (superseded by status).
  Seeds one controlled test template (flobrief_test_notification, status=draft —
  an operator must enter a real Twilio content_sid and flip status to approved
  once Meta has actually approved a real Content Template).
- notification_deliveries: recipient_phone_masked, template_key, idempotency_key,
  queued_at, delivered_at, read_at, failure_category.
- platform_provider_settings: last_connection_check_at, last_connection_status,
  last_connection_error (written only by an explicit connection-verify call).

Revision ID: f3g4h5i6j7k8
Revises: e2f3a4b5c6d7
Create Date: 2026-07-28 00:00:00.000000
"""
from __future__ import annotations

import uuid as _uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3g4h5i6j7k8"
down_revision: Union[str, None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = sa.dialects.postgresql.UUID
JSONB = sa.dialects.postgresql.JSONB


def upgrade() -> None:
    # ── notification_deliveries.status: widen for the new longer status values
    # (e.g. "skipped_template_missing" = 25 chars, "skipped_unverified_phone" =
    # 24 chars) — the original column was VARCHAR(20).
    op.alter_column(
        "notification_deliveries", "status", type_=sa.String(40), existing_type=sa.String(20)
    )

    # ── whatsapp_templates: approved-template registry ──────────────────────────
    op.add_column(
        "whatsapp_templates",
        sa.Column("event_type", sa.String(50), nullable=True),
    )
    op.add_column(
        "whatsapp_templates",
        sa.Column("provider", sa.String(20), nullable=False, server_default="twilio"),
    )
    op.add_column(
        "whatsapp_templates",
        sa.Column("content_sid", sa.String(100), nullable=True),
    )
    op.add_column(
        "whatsapp_templates",
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
    )
    op.add_column(
        "whatsapp_templates",
        sa.Column("variable_schema", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "whatsapp_templates",
        sa.Column(
            "updated_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "whatsapp_templates",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_wat_event_type", "whatsapp_templates", ["event_type"])
    op.drop_column("whatsapp_templates", "is_active")

    # ── notification_deliveries: WhatsApp test-send fields ──────────────────────
    op.add_column(
        "notification_deliveries",
        sa.Column("recipient_phone_masked", sa.String(20), nullable=True),
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("template_key", sa.String(100), nullable=True),
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("idempotency_key", sa.String(100), nullable=True),
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("failure_category", sa.String(30), nullable=True),
    )
    op.create_index(
        "ix_ndel_idempotency_key", "notification_deliveries", ["idempotency_key"]
    )

    # ── platform_provider_settings: real connection-check results ───────────────
    op.add_column(
        "platform_provider_settings",
        sa.Column("last_connection_check_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "platform_provider_settings",
        sa.Column("last_connection_status", sa.String(20), nullable=True),
    )
    op.add_column(
        "platform_provider_settings",
        sa.Column("last_connection_error", sa.String(300), nullable=True),
    )

    # ── Seed the one controlled test template ────────────────────────────────────
    whatsapp_templates_table = sa.table(
        "whatsapp_templates",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("event_type", sa.String),
        sa.column("provider", sa.String),
        sa.column("template_name", sa.String),
        sa.column("language_code", sa.String),
        sa.column("content_sid", sa.String),
        sa.column("status", sa.String),
        sa.column("variable_schema", JSONB),
        sa.column("body", sa.Text),
    )
    op.bulk_insert(
        whatsapp_templates_table,
        [
            {
                "id": _uuid.uuid4(),
                "code": "flobrief_test_notification",
                "event_type": "system.test_notification",
                "provider": "twilio",
                "template_name": "Flobrief Test Bildirimi",
                "language_code": "tr",
                "content_sid": None,
                "status": "draft",
                "variable_schema": {},
                "body": "Flobrief WhatsApp test mesajı. Bu bir test bildirimidir.",
            }
        ],
    )


def downgrade() -> None:
    # Remove the seeded test template row first — otherwise re-running
    # upgrade() would violate the unique constraint on `code`.
    op.execute(
        sa.text("DELETE FROM whatsapp_templates WHERE code = 'flobrief_test_notification'")
    )

    op.drop_column("platform_provider_settings", "last_connection_error")
    # (status width narrowed back at the end of this function, after the
    # longer-status rows referencing it are gone)
    op.drop_column("platform_provider_settings", "last_connection_status")
    op.drop_column("platform_provider_settings", "last_connection_check_at")

    op.drop_index("ix_ndel_idempotency_key", "notification_deliveries")
    op.drop_column("notification_deliveries", "failure_category")
    op.drop_column("notification_deliveries", "read_at")
    op.drop_column("notification_deliveries", "delivered_at")
    op.drop_column("notification_deliveries", "queued_at")
    op.drop_column("notification_deliveries", "idempotency_key")
    op.drop_column("notification_deliveries", "template_key")
    op.drop_column("notification_deliveries", "recipient_phone_masked")

    op.add_column(
        "whatsapp_templates",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.drop_index("ix_wat_event_type", "whatsapp_templates")
    op.drop_column("whatsapp_templates", "approved_at")
    op.drop_column("whatsapp_templates", "updated_by_id")
    op.drop_column("whatsapp_templates", "variable_schema")
    op.drop_column("whatsapp_templates", "status")
    op.drop_column("whatsapp_templates", "content_sid")
    op.drop_column("whatsapp_templates", "provider")
    op.drop_column("whatsapp_templates", "event_type")

    # Deliberately NOT narrowing notification_deliveries.status back to
    # VARCHAR(20): once any row holds one of the new longer status values
    # (e.g. "skipped_template_missing", 25 chars — written by real usage or
    # by tests, and never cleaned up because these are permanent audit rows,
    # not test-only fixtures), narrowing would fail with
    # StringDataRightTruncationError. A one-way column-width increase is the
    # standard, safe approach here — nothing depends on the narrower width.
