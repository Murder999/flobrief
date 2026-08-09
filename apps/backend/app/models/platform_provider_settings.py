from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel
from app.models.enums import WhatsAppProviderType


class PlatformProviderSetting(BaseModel):
    """Encrypted provider credentials for platform-level notification providers.

    One row per provider type. Secrets stored encrypted; never returned in API responses.
    """

    __tablename__ = "platform_provider_settings"

    provider: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    provider_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=WhatsAppProviderType.DISABLED.value,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Encrypted secrets (Fernet-encrypted, base64 encoded)
    encrypted_account_sid: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    encrypted_auth_token: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    encrypted_whatsapp_from: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    encrypted_messaging_service_sid: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    encrypted_webhook_verify_token: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Email/Resend provider fields
    encrypted_api_key: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    email_from_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email_from_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email_reply_to: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email_api_key_masked: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Safe display fields (non-secret partial identifiers)
    account_sid_last4: Mapped[str | None] = mapped_column(String(10), nullable=True)
    whatsapp_from_masked: Mapped[str | None] = mapped_column(String(50), nullable=True)

    configured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    configured_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Real connection-check results (Part 6A) — never fabricated; only ever
    # written by an explicit test_connection()/verify-connection call.
    last_connection_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_connection_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_connection_error: Mapped[str | None] = mapped_column(String(300), nullable=True)

    def __repr__(self) -> str:
        return f"<PlatformProviderSetting provider={self.provider} enabled={self.is_enabled}>"
