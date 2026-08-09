"""WhatsApp provider architecture.

Providers:
  TwilioWhatsAppProvider  — Real Twilio REST API (sandbox or production)
  DisabledWhatsAppProvider — Returns not_configured/skipped; never raises
  WhatsAppProviderFactory  — Loads config from DB, decrypts secrets, returns correct provider
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import NotificationDeliveryStatus
from app.services.secret_encryption import SecretEncryptionError, secret_encryption

_TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"

_E164_RE = re.compile(r"^\+?[1-9]\d{6,14}$")
_WHATSAPP_PREFIX_RE = re.compile(r"^whatsapp:\+?[1-9]\d{6,14}$")

# Twilio's fixed, publicly documented WhatsApp Sandbox sender number — the
# same for every Twilio account. The dev-only freeform test path (Part 6A)
# only ever sends from this exact sender; a project-specific production
# sender never matches it, so this check alone rules out production sends.
TWILIO_SANDBOX_SENDER = "whatsapp:+14155238886"

# Fixed, safe body for the dev-only Sandbox freeform test send. Never
# includes caller/user-supplied text — see send_sandbox_freeform_test_message.
SANDBOX_FREEFORM_TEST_BODY = (
    "Flobrief WhatsApp Sandbox bağlantısı başarıyla çalışıyor. Bu yalnızca "
    "geliştirme ortamında gönderilen bir test mesajıdır."
)


def _normalize_to_whatsapp(phone: str) -> str:
    """Ensure the phone number has the whatsapp: prefix."""
    stripped = phone.strip()
    if stripped.startswith("whatsapp:"):
        return stripped
    if stripped.startswith("+"):
        return f"whatsapp:{stripped}"
    return f"whatsapp:+{stripped}"


def _classify_network_exception(exc: httpx.RequestError) -> str:
    """Classify a failed HTTP call to Twilio itself (as opposed to a non-2xx
    response, which normalize_provider_error handles) — always retryable,
    see whatsapp_retry_policy.RETRYABLE_CATEGORIES."""
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.ConnectError):
        return "connection_error"
    return "network_error"


def _mask_phone(phone: str) -> str:
    """Mask middle digits for logging: +905xxxxxxxx98 → +905***98"""
    clean = phone.replace("whatsapp:", "")
    if len(clean) <= 6:
        return "***"
    return clean[:4] + "***" + clean[-2:]


@dataclass
class WhatsAppDeliveryResult:
    status: str
    provider: str
    provider_message_id: str | None
    error_message: str | None
    # Part 6B-3 — typed classification for the retry worker (see
    # whatsapp_retry_policy.RETRYABLE_CATEGORIES / NON_RETRYABLE_CATEGORIES).
    # None for a successful send; always set on any FAILED result.
    failure_category: str | None = None


@dataclass
class WhatsAppConnectionCheck:
    ok: bool
    provider: str
    detail: str | None = None


@runtime_checkable
class WhatsAppProvider(Protocol):
    def send_message(self, to_phone: str, body: str) -> WhatsAppDeliveryResult: ...

    def send_template_message(
        self, to_phone: str, content_sid: str, variables: dict[str, str]
    ) -> WhatsAppDeliveryResult: ...

    def test_connection(self) -> WhatsAppConnectionCheck: ...

    def get_sender_status(self) -> WhatsAppConnectionCheck: ...

    def validate_config(self) -> bool: ...

    def get_provider_name(self) -> str: ...


class TwilioWhatsAppProvider:
    """Calls Twilio Messages API over HTTPS using Basic Auth.

    Uses httpx (already a project dependency) — no twilio SDK needed.
    """

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        messaging_service_sid: str | None = None,
        sandbox: bool = True,
    ) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from = _normalize_to_whatsapp(from_number)
        self._messaging_service_sid = messaging_service_sid
        self._sandbox = sandbox

    def get_provider_name(self) -> str:
        return "twilio_sandbox" if self._sandbox else "twilio_production"

    def validate_config(self) -> bool:
        return bool(self._account_sid and self._auth_token and self._from)

    def is_official_sandbox_sender(self) -> bool:
        """True only when this provider is configured as sandbox AND its
        `from` number is exactly Twilio's fixed public Sandbox sender —
        never true for a real project-specific WhatsApp Business sender,
        which is what makes this check safe to gate a freeform-text send on."""
        return self._sandbox and self._from == TWILIO_SANDBOX_SENDER

    def send_sandbox_freeform_test_message(self, to_phone: str) -> WhatsAppDeliveryResult:
        """Dev-only Twilio Sandbox free-text send for the WhatsApp test-send
        flow (Part 6A). Always sends the fixed `SANDBOX_FREEFORM_TEST_BODY` —
        never caller/user-supplied text — and never uses a Content SID. All
        environment/consent/recipient gating happens in
        whatsapp_test_send_service before this is ever called; this method
        itself does not re-check APP_ENV, it only refuses to run against a
        non-Sandbox sender.
        """
        if not self.is_official_sandbox_sender():
            return WhatsAppDeliveryResult(
                status=NotificationDeliveryStatus.NOT_CONFIGURED.value,
                provider=self.get_provider_name(),
                provider_message_id=None,
                error_message=(
                    "Sandbox freeform test yalnızca resmi Twilio Sandbox sender ile çalışır."
                ),
            )

        to = _normalize_to_whatsapp(to_phone)
        url = f"{_TWILIO_API_BASE}/Accounts/{self._account_sid}/Messages.json"
        form_data: dict[str, str] = {
            "To": to,
            "From": self._from,
            "Body": SANDBOX_FREEFORM_TEST_BODY,
        }
        if settings.BACKEND_PUBLIC_URL:
            form_data["StatusCallback"] = (
                f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}/api/v1/webhooks/twilio/whatsapp"
            )

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    url,
                    data=form_data,
                    auth=(self._account_sid, self._auth_token),
                )
        except httpx.RequestError as exc:
            return WhatsAppDeliveryResult(
                status=NotificationDeliveryStatus.FAILED.value,
                provider=self.get_provider_name(),
                provider_message_id=None,
                error_message=f"Network error: {type(exc).__name__}",
                failure_category=_classify_network_exception(exc),
            )

        if resp.status_code in (200, 201):
            data = resp.json()
            return WhatsAppDeliveryResult(
                status=NotificationDeliveryStatus.SENT.value,
                provider=self.get_provider_name(),
                provider_message_id=data.get("sid"),
                error_message=None,
            )

        category, safe_msg = self.normalize_provider_error(resp)
        return WhatsAppDeliveryResult(
            status=NotificationDeliveryStatus.FAILED.value,
            provider=self.get_provider_name(),
            provider_message_id=None,
            error_message=safe_msg,
            failure_category=category,
        )

    def send_message(self, to_phone: str, body: str) -> WhatsAppDeliveryResult:
        to = _normalize_to_whatsapp(to_phone)
        url = f"{_TWILIO_API_BASE}/Accounts/{self._account_sid}/Messages.json"

        form_data: dict[str, str] = {
            "To": to,
            "Body": body,
        }
        if self._messaging_service_sid:
            form_data["MessagingServiceSid"] = self._messaging_service_sid
        else:
            form_data["From"] = self._from

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    url,
                    data=form_data,
                    auth=(self._account_sid, self._auth_token),
                )
        except httpx.RequestError as exc:
            return WhatsAppDeliveryResult(
                status=NotificationDeliveryStatus.FAILED.value,
                provider=self.get_provider_name(),
                provider_message_id=None,
                error_message=f"Network error: {type(exc).__name__}",
                failure_category=_classify_network_exception(exc),
            )

        if resp.status_code in (200, 201):
            data = resp.json()
            return WhatsAppDeliveryResult(
                status=NotificationDeliveryStatus.SENT.value,
                provider=self.get_provider_name(),
                provider_message_id=data.get("sid"),
                error_message=None,
            )

        category, safe_msg = self.normalize_provider_error(resp)
        return WhatsAppDeliveryResult(
            status=NotificationDeliveryStatus.FAILED.value,
            provider=self.get_provider_name(),
            provider_message_id=None,
            error_message=safe_msg,
            failure_category=category,
        )

    def send_template_message(
        self, to_phone: str, content_sid: str, variables: dict[str, str]
    ) -> WhatsAppDeliveryResult:
        """Send an approved WhatsApp Business template via Twilio Content API.

        Unlike send_message(), this does not send free text — it references a
        pre-approved Content Template by SID, which is what real Meta/WhatsApp
        Business sends outside a session window require.
        """
        to = _normalize_to_whatsapp(to_phone)
        url = f"{_TWILIO_API_BASE}/Accounts/{self._account_sid}/Messages.json"

        form_data: dict[str, str] = {
            "To": to,
            "ContentSid": content_sid,
        }
        if variables:
            form_data["ContentVariables"] = json.dumps(variables)
        if self._messaging_service_sid:
            form_data["MessagingServiceSid"] = self._messaging_service_sid
        else:
            form_data["From"] = self._from

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    url,
                    data=form_data,
                    auth=(self._account_sid, self._auth_token),
                )
        except httpx.RequestError as exc:
            return WhatsAppDeliveryResult(
                status=NotificationDeliveryStatus.FAILED.value,
                provider=self.get_provider_name(),
                provider_message_id=None,
                error_message=f"Network error: {type(exc).__name__}",
                failure_category=_classify_network_exception(exc),
            )

        if resp.status_code in (200, 201):
            data = resp.json()
            return WhatsAppDeliveryResult(
                status=NotificationDeliveryStatus.SENT.value,
                provider=self.get_provider_name(),
                provider_message_id=data.get("sid"),
                error_message=None,
            )

        category, safe_msg = self.normalize_provider_error(resp)
        return WhatsAppDeliveryResult(
            status=NotificationDeliveryStatus.FAILED.value,
            provider=self.get_provider_name(),
            provider_message_id=None,
            error_message=safe_msg,
            failure_category=category,
        )

    def test_connection(self) -> WhatsAppConnectionCheck:
        """Real, cheap credential check — a single GET on the account resource.
        Not a send; no retry loop (safe to call from within an API request)."""
        url = f"{_TWILIO_API_BASE}/Accounts/{self._account_sid}.json"
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(url, auth=(self._account_sid, self._auth_token))
        except httpx.RequestError as exc:
            return WhatsAppConnectionCheck(
                ok=False,
                provider=self.get_provider_name(),
                detail=f"Network error: {type(exc).__name__}",
            )
        if resp.status_code == 200:
            return WhatsAppConnectionCheck(ok=True, provider=self.get_provider_name())
        _category, safe_msg = self.normalize_provider_error(resp)
        return WhatsAppConnectionCheck(ok=False, provider=self.get_provider_name(), detail=safe_msg)

    def get_sender_status(self) -> WhatsAppConnectionCheck:
        """Validates the configured sender is present and the account is reachable.

        Twilio's REST API does not expose a direct "is this WhatsApp sender
        Meta-approved" check outside Business Manager — this call verifies what
        is actually verifiable here (account credentials + a configured
        from-number/messaging-service) and is honest about that boundary rather
        than fabricating a deeper guarantee.
        """
        if not self._from and not self._messaging_service_sid:
            return WhatsAppConnectionCheck(
                ok=False,
                provider=self.get_provider_name(),
                detail="No whatsapp_from or messaging_service_sid configured",
            )
        return self.test_connection()

    @staticmethod
    def normalize_provider_error(resp: httpx.Response) -> tuple[str, str]:
        """Map a Twilio error response to (failure_category, safe_message).

        safe_message never contains a phone number or secret — Twilio error
        bodies for this API do not echo the Auth Token, and any "to"/"from"
        number is stripped defensively.
        """
        try:
            data = resp.json()
            raw_msg = str(data.get("message", f"HTTP {resp.status_code}"))
        except Exception:
            raw_msg = f"HTTP {resp.status_code}"
        safe_msg = re.sub(r"\+?\d{7,15}", "***", raw_msg)[:200]

        if resp.status_code in (401, 403):
            category = "auth"
        elif resp.status_code == 429:
            category = "rate_limited"
        elif resp.status_code == 400:
            category = "invalid_recipient"
        elif resp.status_code >= 500:
            category = "server_error"
        else:
            category = "unknown"
        return category, f"Twilio error {resp.status_code}: {safe_msg}"


class DisabledWhatsAppProvider:
    """Returned when provider is not configured or disabled. Never raises."""

    def get_provider_name(self) -> str:
        return "disabled"

    def validate_config(self) -> bool:
        return False

    def send_message(self, to_phone: str, body: str) -> WhatsAppDeliveryResult:
        return WhatsAppDeliveryResult(
            status=NotificationDeliveryStatus.NOT_CONFIGURED.value,
            provider=self.get_provider_name(),
            provider_message_id=None,
            error_message="WhatsApp provider not configured",
        )

    def send_template_message(
        self, to_phone: str, content_sid: str, variables: dict[str, str]
    ) -> WhatsAppDeliveryResult:
        return WhatsAppDeliveryResult(
            status=NotificationDeliveryStatus.NOT_CONFIGURED.value,
            provider=self.get_provider_name(),
            provider_message_id=None,
            error_message="WhatsApp provider not configured",
        )

    def test_connection(self) -> WhatsAppConnectionCheck:
        return WhatsAppConnectionCheck(
            ok=False, provider=self.get_provider_name(), detail="WhatsApp provider not configured"
        )

    def get_sender_status(self) -> WhatsAppConnectionCheck:
        return self.test_connection()

    def skipped(self) -> WhatsAppDeliveryResult:
        return WhatsAppDeliveryResult(
            status=NotificationDeliveryStatus.SKIPPED.value,
            provider=self.get_provider_name(),
            provider_message_id=None,
            error_message="WhatsApp notifications disabled for this user",
        )


class WhatsAppProviderFactory:
    """Loads provider settings from DB, decrypts secrets, returns correct provider.

    Decrypted secrets exist only within the provider instance lifetime.
    Never stored, never logged, never returned to API callers.
    """

    @staticmethod
    async def get_provider(db: AsyncSession) -> TwilioWhatsAppProvider | DisabledWhatsAppProvider:
        from sqlalchemy import select

        from app.models.enums import WhatsAppProviderType
        from app.models.platform_provider_settings import PlatformProviderSetting

        if not settings.WHATSAPP_NOTIFICATIONS_ENABLED:
            return DisabledWhatsAppProvider()

        stmt = select(PlatformProviderSetting).where(
            PlatformProviderSetting.provider == "whatsapp_twilio",
            PlatformProviderSetting.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()

        if row is None or not row.is_enabled:
            return DisabledWhatsAppProvider()

        if row.provider_type == WhatsAppProviderType.DISABLED.value:
            return DisabledWhatsAppProvider()

        # Decrypt secrets for runtime use only
        try:
            account_sid = secret_encryption.decrypt(row.encrypted_account_sid or "")
            auth_token = secret_encryption.decrypt(row.encrypted_auth_token or "")
            from_number = secret_encryption.decrypt(row.encrypted_whatsapp_from or "")
            msid = (
                secret_encryption.decrypt(row.encrypted_messaging_service_sid)
                if row.encrypted_messaging_service_sid
                else None
            )
        except SecretEncryptionError:
            return DisabledWhatsAppProvider()

        is_sandbox = row.provider_type == WhatsAppProviderType.TWILIO_SANDBOX.value

        return TwilioWhatsAppProvider(
            account_sid=account_sid,
            auth_token=auth_token,
            from_number=from_number,
            messaging_service_sid=msid,
            sandbox=is_sandbox,
        )


# Legacy compat — passive provider for code that hasn't been migrated yet
class PassiveWhatsAppProvider(DisabledWhatsAppProvider):
    def send(self, to_phone: str, template_body: str) -> WhatsAppDeliveryResult:
        return self.send_message(to_phone, template_body)


whatsapp_provider = PassiveWhatsAppProvider()
