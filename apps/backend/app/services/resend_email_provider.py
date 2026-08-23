"""Resend email provider.

Providers:
  ResendEmailProvider  — Real Resend API via httpx.AsyncClient
  DisabledEmailProvider — Returns not_configured/skipped; never raises
  EmailProviderFactory  — Loads config from DB, decrypts secrets, returns correct provider

Security: API key never logged or returned in API responses. DB value is Fernet-encrypted.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import NotificationDeliveryStatus
from app.services.secret_encryption import SecretEncryptionError, secret_encryption

_RESEND_API = "https://api.resend.com/emails"
_EMAIL_PROVIDER_KEY = "email_resend"
logger = logging.getLogger(__name__)


def _map_resend_error(status_code: int, err_name: str, err_msg: str) -> str:
    raw = f"[Resend {status_code}: {err_name or '?'} — {err_msg[:300]}]"
    if status_code == 401:
        return f"HTTP 401 — API anahtarı geçersiz veya eksik. {raw}"
    if status_code == 403:
        # 403 can mean: domain not verified, restricted API key, or permission denied.
        msg_lower = err_msg.lower()
        name_lower = err_name.lower()
        if "domain" in msg_lower or "sender" in msg_lower or "from" in msg_lower:
            return f"HTTP 403 — From e-posta domain'i Resend'de doğrulanmamış. {raw}"
        if "restricted" in name_lower or "permission" in msg_lower:
            return f"HTTP 403 — API anahtarının gönderme izni yok. {raw}"
        return f"HTTP 403 — Resend erişim reddetti. {raw}"
    if status_code == 422:
        msg_lower = err_msg.lower()
        if "from" in msg_lower or "domain" in msg_lower or "sender" in msg_lower:
            return f"HTTP 422 — From e-posta alanı geçersiz veya domain doğrulanmamış. {raw}"
        return f"HTTP 422 — Geçersiz istek. {raw}"
    if status_code == 429:
        return f"HTTP 429 — Resend istek limiti aşıldı. {raw}"
    return f"HTTP {status_code} — Resend hatası. {raw}"


@dataclass
class EmailDeliveryResult:
    status: str
    provider: str
    provider_message_id: str | None
    error_message: str | None


class ResendEmailProvider:
    """Calls Resend REST API over HTTPS using httpx.AsyncClient.

    API key never stored after construction. Only used within async context.
    """

    def __init__(
        self,
        api_key: str,
        from_name: str,
        from_email: str,
        reply_to: str | None = None,
        test_mode: bool = False,
        test_recipient: str = "delivered@resend.dev",
        test_from_email: str = "onboarding@resend.dev",
    ) -> None:
        self._api_key = api_key
        self._from_name = from_name
        self._from_email = from_email
        self._reply_to = reply_to
        self._test_mode = test_mode
        self._test_recipient = test_recipient
        self._test_from_email = test_from_email

    def get_provider_name(self) -> str:
        return "resend"

    def is_active(self) -> bool:
        return bool(self._api_key and self._from_email)

    async def send(
        self,
        to_email: str,
        subject: str,
        html: str,
        text: str | None = None,
        reply_to: str | None = None,
    ) -> EmailDeliveryResult:
        effective_from_email = self._test_from_email if self._test_mode else self._from_email
        effective_to_email = self._test_recipient if self._test_mode else to_email
        effective_subject = f"[TEST → {to_email}] {subject}" if self._test_mode else subject
        from_address = (
            f"{self._from_name} <{effective_from_email}>"
            if self._from_name
            else effective_from_email
        )
        payload: dict[str, object] = {
            "from": from_address,
            "to": [effective_to_email],
            "subject": effective_subject,
            "html": html,
        }
        if text:
            payload["text"] = text
        effective_reply_to = reply_to or self._reply_to
        if effective_reply_to:
            payload["reply_to"] = effective_reply_to

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    _RESEND_API,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                )
        except httpx.RequestError as exc:
            return EmailDeliveryResult(
                status=NotificationDeliveryStatus.FAILED.value,
                provider="resend",
                provider_message_id=None,
                error_message=f"Network error: {type(exc).__name__}",
            )

        if resp.status_code in (200, 201):
            try:
                data = resp.json()
            except ValueError:
                data = {}
            return EmailDeliveryResult(
                status=NotificationDeliveryStatus.SENT.value,
                provider="resend",
                provider_message_id=data.get("id"),
                error_message=None,
            )

        try:
            err_data = resp.json()
            err_name = err_data.get("name", "")
            err_msg = err_data.get("message", f"HTTP {resp.status_code}")
        except Exception:
            err_name = ""
            err_msg = f"HTTP {resp.status_code}"

        return EmailDeliveryResult(
            status=NotificationDeliveryStatus.FAILED.value,
            provider="resend",
            provider_message_id=None,
            error_message=_map_resend_error(resp.status_code, err_name, err_msg),
        )


class DisabledEmailProvider:
    """Returned when provider is not configured or disabled. Never raises."""

    def get_provider_name(self) -> str:
        return "disabled"

    def is_active(self) -> bool:
        return False

    async def send(
        self,
        to_email: str,
        subject: str,
        html: str,
        text: str | None = None,
        reply_to: str | None = None,
    ) -> EmailDeliveryResult:
        return EmailDeliveryResult(
            status=NotificationDeliveryStatus.NOT_CONFIGURED.value,
            provider="disabled",
            provider_message_id=None,
            error_message="Email provider not configured",
        )


class EmailProviderFactory:
    """Loads provider config from DB, decrypts secrets, returns correct provider.

    Production environment config is authoritative when present, so a stale
    DB row cannot disable or replace the server-managed credential. Outside
    production, a valid and enabled DB config takes priority and environment
    config remains the fallback.
    Decrypted API key exists only within the provider instance lifetime.
    """

    @staticmethod
    async def get_provider(
        db: AsyncSession,
        *,
        ignore_enabled: bool = False,
    ) -> ResendEmailProvider | DisabledEmailProvider:
        """Return the configured email provider.

        ignore_enabled=True: used by the test endpoint so admins can verify a key
        even when the provider is not yet enabled in production.
        """
        from sqlalchemy import select

        from app.models.platform_provider_settings import PlatformProviderSetting

        env_is_configured = bool(settings.RESEND_API_KEY and settings.EMAIL_FROM)
        if settings.is_production and env_is_configured and not ignore_enabled:
            return EmailProviderFactory._from_environment()

        stmt = select(PlatformProviderSetting).where(
            PlatformProviderSetting.provider == _EMAIL_PROVIDER_KEY,
            PlatformProviderSetting.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()

        if row is not None and row.encrypted_api_key and (ignore_enabled or row.is_enabled):
            try:
                api_key = secret_encryption.decrypt(row.encrypted_api_key)
                return ResendEmailProvider(
                    api_key=api_key,
                    from_name=row.email_from_name or settings.EMAIL_FROM_NAME,
                    from_email=row.email_from_email or settings.EMAIL_FROM,
                    reply_to=row.email_reply_to or None,
                    test_mode=settings.RESEND_TEST_MODE,
                    test_recipient=settings.RESEND_TEST_RECIPIENT,
                    test_from_email=settings.RESEND_TEST_FROM_EMAIL,
                )
            except SecretEncryptionError as exc:
                logger.warning(
                    "Email provider DB secret could not be decrypted; "
                    "falling back to environment configuration "
                    "provider=resend error_type=%s",
                    type(exc).__name__,
                )

        if env_is_configured:
            return EmailProviderFactory._from_environment()

        return DisabledEmailProvider()

    @staticmethod
    def _from_environment() -> ResendEmailProvider:
        return ResendEmailProvider(
            api_key=settings.RESEND_API_KEY,
            from_name=settings.EMAIL_FROM_NAME,
            from_email=settings.EMAIL_FROM,
            reply_to=settings.EMAIL_REPLY_TO or None,
            test_mode=settings.RESEND_TEST_MODE,
            test_recipient=settings.RESEND_TEST_RECIPIENT,
            test_from_email=settings.RESEND_TEST_FROM_EMAIL,
        )
