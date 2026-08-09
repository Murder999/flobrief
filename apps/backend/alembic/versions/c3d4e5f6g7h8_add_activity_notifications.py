"""add activity logs and notifications

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-07-08 14:00:00.000000

"""

from __future__ import annotations

import textwrap

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6g7h8"
down_revision = "b2c3d4e5f6g7"
branch_labels = None
depends_on = None

UUID = sa.dialects.postgresql.UUID
JSONB = sa.dialects.postgresql.JSONB


def upgrade() -> None:
    # ── activity_logs (immutable, no FK constraints, no updated_at/deleted_at) ──
    op.create_table(
        "activity_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("agency_id", UUID(as_uuid=True), nullable=True),
        sa.Column("brand_id", UUID(as_uuid=True), nullable=True),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("meta", JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
    )
    op.create_index("ix_act_agency_id", "activity_logs", ["agency_id"])
    op.create_index("ix_act_entity", "activity_logs", ["entity_type", "entity_id"])
    op.create_index("ix_act_actor", "activity_logs", ["actor_user_id"])

    # ── notification_events ────────────────────────────────────────────────────
    op.create_table(
        "notification_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("agency_id", UUID(as_uuid=True),
                  sa.ForeignKey("agencies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("brand_id", UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_nev_agency_id", "notification_events", ["agency_id"])
    op.create_index("ix_nev_processed", "notification_events", ["processed_at"])

    # ── notifications ──────────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agency_id", UUID(as_uuid=True),
                  sa.ForeignKey("agencies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("brand_id", UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_id", UUID(as_uuid=True),
                  sa.ForeignKey("notification_events.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notif_user_id", "notifications", ["user_id"])
    op.create_index("ix_notif_agency_id", "notifications", ["agency_id"])
    op.create_index("ix_notif_is_read", "notifications", ["is_read"])

    # ── notification_preferences ───────────────────────────────────────────────
    op.create_table(
        "notification_preferences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("email_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("whatsapp_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("in_app_enabled", sa.Boolean, nullable=False, server_default="true"),
    )
    op.create_index("ix_npref_user_id", "notification_preferences", ["user_id"], unique=True)

    # ── notification_deliveries ────────────────────────────────────────────────
    op.create_table(
        "notification_deliveries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notification_id", UUID(as_uuid=True),
                  sa.ForeignKey("notifications.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_id", UUID(as_uuid=True),
                  sa.ForeignKey("notification_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False, server_default="''"),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ndel_event_id", "notification_deliveries", ["event_id"])
    op.create_index("ix_ndel_notification_id", "notification_deliveries", ["notification_id"])

    # ── email_templates ────────────────────────────────────────────────────────
    op.create_table(
        "email_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body_html", sa.Text, nullable=False),
        sa.Column("body_text", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )

    # ── whatsapp_templates ─────────────────────────────────────────────────────
    op.create_table(
        "whatsapp_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("template_name", sa.String(200), nullable=False),
        sa.Column("language_code", sa.String(10), nullable=False, server_default="'tr'"),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )

    # ── Seed email templates ───────────────────────────────────────────────────
    _seed_email_templates()


def _seed_email_templates() -> None:
    base_html = textwrap.dedent("""\
        <!DOCTYPE html>
        <html lang="tr">
        <body style="margin:0;padding:40px;font-family:-apple-system,BlinkMacSystemFont,'Inter',Arial,sans-serif;background:#0A0A0F;color:#F0F0F8;">
        <div style="max-width:480px;margin:0 auto;background:#111118;border:1px solid #2A2A3A;border-radius:12px;padding:32px;">
        <h1 style="color:#6366F1;font-size:24px;margin-bottom:16px;">Flobrief</h1>
        <h2 style="font-size:18px;margin-bottom:16px;">$title</h2>
        <p style="color:#8888A8;line-height:1.6;margin-bottom:24px;">$body</p>
        <a href="$action_url" style="display:inline-block;background:#6366F1;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">$action_label</a>
        <p style="color:#8888A8;font-size:12px;margin-top:32px;border-top:1px solid #2A2A3A;padding-top:16px;">
          Bu e-posta Flobrief tarafından otomatik gönderilmiştir.
        </p>
        </div>
        </body>
        </html>""")

    templates = [
        {
            "code": "user.invited",
            "subject": "Flobrief — $agency_name Davetiyesi",
            "body_html": base_html,
            "body_text": "$title\n\n$body\n\n$action_url",
        },
        {
            "code": "brief.submitted_for_approval",
            "subject": "Flobrief — Onay İsteği: $brief_title",
            "body_html": base_html,
            "body_text": "$title\n\n$body\n\n$action_url",
        },
        {
            "code": "brief.revision_requested",
            "subject": "Flobrief — Revizyon İstendi: $brief_title",
            "body_html": base_html,
            "body_text": "$title\n\n$body\n\n$action_url",
        },
        {
            "code": "brief.approved",
            "subject": "Flobrief — Onaylandı: $brief_title",
            "body_html": base_html,
            "body_text": "$title\n\n$body\n\n$action_url",
        },
        {
            "code": "subscription.payment_failed",
            "subject": "Flobrief — Ödeme Başarısız",
            "body_html": base_html,
            "body_text": "$title\n\n$body\n\n$action_url",
        },
    ]

    email_templates_table = sa.table(
        "email_templates",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("subject", sa.String),
        sa.column("body_html", sa.Text),
        sa.column("body_text", sa.Text),
        sa.column("is_active", sa.Boolean),
    )

    import uuid as _uuid

    op.bulk_insert(
        email_templates_table,
        [
            {
                "id": _uuid.uuid4(),
                "code": t["code"],
                "subject": t["subject"],
                "body_html": t["body_html"],
                "body_text": t["body_text"],
                "is_active": True,
            }
            for t in templates
        ],
    )


def downgrade() -> None:
    op.drop_table("whatsapp_templates")
    op.drop_table("email_templates")
    op.drop_index("ix_ndel_notification_id", "notification_deliveries")
    op.drop_index("ix_ndel_event_id", "notification_deliveries")
    op.drop_table("notification_deliveries")
    op.drop_index("ix_npref_user_id", "notification_preferences")
    op.drop_table("notification_preferences")
    op.drop_index("ix_notif_is_read", "notifications")
    op.drop_index("ix_notif_agency_id", "notifications")
    op.drop_index("ix_notif_user_id", "notifications")
    op.drop_table("notifications")
    op.drop_index("ix_nev_processed", "notification_events")
    op.drop_index("ix_nev_agency_id", "notification_events")
    op.drop_table("notification_events")
    op.drop_index("ix_act_actor", "activity_logs")
    op.drop_index("ix_act_entity", "activity_logs")
    op.drop_index("ix_act_agency_id", "activity_logs")
    op.drop_table("activity_logs")
