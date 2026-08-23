"""add_whatsapp_infra

Adds:
- platform_provider_settings table (encrypted Twilio credentials)
- users: phone_number, phone_verified_at, whatsapp_opt_in, whatsapp_opt_in_at, whatsapp_opt_out_at
- notification_deliveries: attempt_count, failed_at, next_retry_at

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-07-10 14:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "l2m3n4o5p6q7"
down_revision: Union[str, None] = "k1l2m3n4o5p6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── platform_provider_settings ─────────────────────────────────────────────
    op.create_table(
        "platform_provider_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_type", sa.String(50), nullable=False, server_default="disabled"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("encrypted_account_sid", sa.String(1000), nullable=True),
        sa.Column("encrypted_auth_token", sa.String(1000), nullable=True),
        sa.Column("encrypted_whatsapp_from", sa.String(1000), nullable=True),
        sa.Column("encrypted_messaging_service_sid", sa.String(1000), nullable=True),
        sa.Column("encrypted_webhook_verify_token", sa.String(1000), nullable=True),
        sa.Column("account_sid_last4", sa.String(10), nullable=True),
        sa.Column("whatsapp_from_masked", sa.String(50), nullable=True),
        sa.Column("configured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "configured_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_platform_provider_settings_provider", "platform_provider_settings", ["provider"]
    )
    op.create_index(
        "ix_platform_provider_settings_provider",
        "platform_provider_settings",
        ["provider"],
    )

    # ── users: WhatsApp / phone fields ─────────────────────────────────────────
    op.add_column("users", sa.Column("phone_number", sa.String(30), nullable=True))
    op.add_column(
        "users", sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users", sa.Column("whatsapp_opt_in", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column(
        "users", sa.Column("whatsapp_opt_in_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users", sa.Column("whatsapp_opt_out_at", sa.DateTime(timezone=True), nullable=True)
    )

    # ── notification_deliveries: retry tracking ────────────────────────────────
    op.add_column(
        "notification_deliveries",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notification_deliveries", "next_retry_at")
    op.drop_column("notification_deliveries", "failed_at")
    op.drop_column("notification_deliveries", "attempt_count")

    op.drop_column("users", "whatsapp_opt_out_at")
    op.drop_column("users", "whatsapp_opt_in_at")
    op.drop_column("users", "whatsapp_opt_in")
    op.drop_column("users", "phone_verified_at")
    op.drop_column("users", "phone_number")

    op.drop_index("ix_platform_provider_settings_provider", table_name="platform_provider_settings")
    op.drop_constraint(
        "uq_platform_provider_settings_provider", "platform_provider_settings", type_="unique"
    )
    op.drop_table("platform_provider_settings")
