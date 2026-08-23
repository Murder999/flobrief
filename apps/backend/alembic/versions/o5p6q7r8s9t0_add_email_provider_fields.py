"""add_email_provider_fields

Adds:
- platform_provider_settings: encrypted_api_key, email_from_name, email_from_email,
  email_reply_to, email_api_key_masked columns for Resend email provider
- notification_deliveries: recipient_email column for delivery tracking

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-07-11 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "o5p6q7r8s9t0"
down_revision = "n4o5p6q7r8s9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── platform_provider_settings — email/Resend columns ─────────────────────
    op.add_column(
        "platform_provider_settings", sa.Column("encrypted_api_key", sa.String(1000), nullable=True)
    )
    op.add_column(
        "platform_provider_settings", sa.Column("email_from_name", sa.String(200), nullable=True)
    )
    op.add_column(
        "platform_provider_settings", sa.Column("email_from_email", sa.String(200), nullable=True)
    )
    op.add_column(
        "platform_provider_settings", sa.Column("email_reply_to", sa.String(200), nullable=True)
    )
    op.add_column(
        "platform_provider_settings",
        sa.Column("email_api_key_masked", sa.String(30), nullable=True),
    )

    # ── notification_deliveries — recipient_email ──────────────────────────────
    op.add_column(
        "notification_deliveries", sa.Column("recipient_email", sa.String(255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("notification_deliveries", "recipient_email")
    op.drop_column("platform_provider_settings", "email_api_key_masked")
    op.drop_column("platform_provider_settings", "email_reply_to")
    op.drop_column("platform_provider_settings", "email_from_email")
    op.drop_column("platform_provider_settings", "email_from_name")
    op.drop_column("platform_provider_settings", "encrypted_api_key")
