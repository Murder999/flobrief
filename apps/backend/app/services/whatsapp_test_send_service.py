"""Single orchestration point for the tenant Owner/Admin WhatsApp test-send.

No recipient is ever accepted from the caller (see docs/DECISIONS.md
DECISION-049) — the target phone is always either the requesting user's own
opted-in `phone_number`, or (non-production only) the platform's fixed
WHATSAPP_TEST_RECIPIENT allowlist. Every branch is honest: a skip is recorded
and returned as a skip, never silently upgraded into a fake success.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limiter import rate_limit_whatsapp_test_send
from app.models.agency import Agency
from app.models.enums import NotificationChannel, NotificationDeliveryStatus
from app.models.user import User
from app.repositories.activity import ActivityLogRepository
from app.repositories.notification import (
    NotificationDeliveryRepository,
    NotificationEventRepository,
    NotificationPreferenceRepository,
)
from app.repositories.whatsapp_template import WhatsAppTemplateRepository
from app.services.phone_utils import mask_phone_e164 as _mask_phone
from app.services.phone_utils import normalize_e164
from app.services.whatsapp_provider import (
    DisabledWhatsAppProvider,
    TwilioWhatsAppProvider,
    WhatsAppProviderFactory,
)

_TEST_TEMPLATE_CODE = "flobrief_test_notification"
_TEST_EVENT_TYPE = "system.test_notification"
# Dev-only Twilio Sandbox freeform fallback template_key (Part 6A) — used only
# when _sandbox_freeform_test_eligible() passes; never a stand-in for a real
# approved-template record (see docs/DECISIONS.md).
_SANDBOX_FREEFORM_TEMPLATE_KEY = "sandbox_freeform_test"


@dataclass
class WhatsAppTestSendOutcome:
    delivery_id: uuid.UUID | None
    masked_recipient: str | None
    status: str
    provider: str
    template_key: str
    provider_message_id: str | None
    safe_error: str | None


class _Recorder:
    """Bundles the event/delivery/audit-log repos so every branch persists
    the same way — a real DB row per attempt, never an in-memory-only result."""

    def __init__(self, db: AsyncSession, agency: Agency, user: User) -> None:
        self.db = db
        self.agency = agency
        self.user = user
        self.event_repo = NotificationEventRepository(db)
        self.delivery_repo = NotificationDeliveryRepository(db)
        self.audit_repo = ActivityLogRepository(db)

    async def record(
        self,
        *,
        status: str,
        provider: str,
        template_key: str | None = None,
        phone: str | None = None,
        provider_message_id: str | None = None,
        error_message: str | None = None,
        failure_category: str | None = None,
    ) -> WhatsAppTestSendOutcome:
        event = await self.event_repo.create(
            event_type=_TEST_EVENT_TYPE,
            payload={"summary": "WhatsApp bağlantı testi"},
            agency_id=self.agency.id,
            actor_user_id=self.user.id,
        )
        now = datetime.now(UTC)
        is_sent = status == NotificationDeliveryStatus.SENT.value
        delivery = await self.delivery_repo.create(
            event_id=event.id,
            channel=NotificationChannel.WHATSAPP.value,
            status=status,
            provider=provider,
            provider_message_id=provider_message_id,
            error_message=error_message,
            recipient_phone_masked=_mask_phone(phone) if phone else None,
            recipient_user_id=self.user.id,
            template_key=template_key,
            idempotency_key=f"wa-test:{self.user.id}:{uuid.uuid4()}",
            queued_at=now,
            sent_at=now if is_sent else None,
            failure_category=failure_category,
        )
        await self.event_repo.mark_processed(event)

        await self.audit_repo.create(
            action="whatsapp.test_send",
            entity_type="notification_delivery",
            entity_id=delivery.id,
            agency_id=self.agency.id,
            actor_user_id=self.user.id,
            meta={"status": status, "template_key": template_key, "provider": provider},
        )
        await self.db.commit()

        return WhatsAppTestSendOutcome(
            delivery_id=delivery.id,
            masked_recipient=_mask_phone(phone) if phone else None,
            status=status,
            provider=provider,
            template_key=template_key or _TEST_TEMPLATE_CODE,
            provider_message_id=provider_message_id,
            safe_error=error_message,
        )


def _sandbox_freeform_test_eligible(
    provider: TwilioWhatsAppProvider | DisabledWhatsAppProvider,
) -> bool:
    """Dev-only fallback gate for the WhatsApp test-send flow (Part 6A),
    consulted only after the approved-template gate has already failed.

    Every condition must hold; this never widens what staging/production can
    do — APP_ENV alone already rules those out, and each remaining check
    (feature flag, official Sandbox sender, a configured test recipient) is
    independently required. See docs/DECISIONS.md.
    """
    if not settings.is_development:
        return False
    if not settings.WHATSAPP_NOTIFICATIONS_ENABLED:
        return False
    if not settings.WHATSAPP_SANDBOX_FREEFORM_TEST_ENABLED:
        return False
    if not isinstance(provider, TwilioWhatsAppProvider):
        return False
    if not provider.is_official_sandbox_sender():
        return False
    return bool(settings.WHATSAPP_TEST_RECIPIENT)


async def send_test_message(
    db: AsyncSession,
    *,
    agency: Agency,
    user: User,
) -> WhatsAppTestSendOutcome:
    recorder = _Recorder(db, agency, user)
    pref_repo = NotificationPreferenceRepository(db)
    template_repo = WhatsAppTemplateRepository(db)

    # 1. Demo tenant — never a real external send, regardless of consent state.
    if agency.is_demo:
        return await recorder.record(
            status=NotificationDeliveryStatus.SKIPPED_DEMO_TENANT.value,
            provider="disabled",
            error_message="Demo tenant'ta WhatsApp test mesajı gönderilemez.",
        )

    # 2. Consent — phone presence alone is never sufficient.
    pref = await pref_repo.get_or_create(user.id)
    if not pref.whatsapp_enabled or not user.whatsapp_opt_in:
        return await recorder.record(
            status=NotificationDeliveryStatus.SKIPPED_NO_CONSENT.value,
            provider="disabled",
            error_message="WhatsApp bildirimleri için onayınız yok.",
        )

    # 3. Phone resolution — user's own opted-in number, or (non-prod only) the
    #    platform's fixed test-recipient allowlist. No other source.
    raw_phone = user.phone_number
    if not raw_phone and not settings.is_production and settings.WHATSAPP_TEST_RECIPIENT:
        raw_phone = settings.WHATSAPP_TEST_RECIPIENT
    if not raw_phone:
        return await recorder.record(
            status=NotificationDeliveryStatus.SKIPPED_NO_PHONE.value,
            provider="disabled",
            error_message="Profilinizde kayıtlı bir telefon numarası yok.",
        )

    phone = normalize_e164(raw_phone)
    if phone is None:
        return await recorder.record(
            status=NotificationDeliveryStatus.FAILED.value,
            provider="disabled",
            error_message="Telefon numarası geçerli bir E.164 formatında değil.",
            failure_category="invalid_recipient",
        )

    # 4. Rate limit — after cheap checks, before any provider/network call.
    await rate_limit_whatsapp_test_send(str(user.id))

    # 5. Approved-template gate.
    template = await template_repo.get_approved(
        _TEST_TEMPLATE_CODE,
        locale=settings.WHATSAPP_DEFAULT_LOCALE,
        provider="twilio",
    )

    # 6. Provider — resolved once, used by both the approved-template send
    #    below and the dev-only Sandbox freeform fallback further down.
    provider = await WhatsAppProviderFactory.get_provider(db)

    if template is not None:
        if isinstance(provider, DisabledWhatsAppProvider):
            return await recorder.record(
                status=NotificationDeliveryStatus.NOT_CONFIGURED.value,
                provider=provider.get_provider_name(),
                template_key=template.code,
                phone=phone,
                error_message="WhatsApp sağlayıcısı yapılandırılmamış.",
            )

        try:
            result = provider.send_template_message(phone, template.content_sid or "", {})
        except Exception as exc:  # pragma: no cover - defensive, provider never raises today
            return await recorder.record(
                status=NotificationDeliveryStatus.FAILED.value,
                provider=provider.get_provider_name(),
                template_key=template.code,
                phone=phone,
                error_message=f"Beklenmeyen hata: {type(exc).__name__}",
                failure_category="unknown",
            )

        is_sent = result.status == NotificationDeliveryStatus.SENT.value
        return await recorder.record(
            status=result.status,
            provider=result.provider,
            template_key=template.code,
            phone=phone,
            provider_message_id=result.provider_message_id,
            error_message=result.error_message,
            failure_category=None if is_sent else "provider",
        )

    # 7. No approved template — dev-only Twilio Sandbox freeform fallback.
    #    The recipient here is always the platform's fixed
    #    WHATSAPP_TEST_RECIPIENT, never `phone` from step 3 (which may be the
    #    user's own number) — no request body field for a recipient exists at
    #    all (see docs/DECISIONS.md DECISION-049), and this fallback narrows
    #    the sandbox target further still.
    if isinstance(provider, TwilioWhatsAppProvider) and _sandbox_freeform_test_eligible(provider):
        sandbox_recipient = normalize_e164(settings.WHATSAPP_TEST_RECIPIENT or "")
        if sandbox_recipient is not None:
            try:
                result = provider.send_sandbox_freeform_test_message(sandbox_recipient)
            except Exception as exc:  # pragma: no cover - defensive, provider never raises today
                return await recorder.record(
                    status=NotificationDeliveryStatus.FAILED.value,
                    provider=provider.get_provider_name(),
                    template_key=_SANDBOX_FREEFORM_TEMPLATE_KEY,
                    phone=sandbox_recipient,
                    error_message=f"Beklenmeyen hata: {type(exc).__name__}",
                    failure_category="unknown",
                )

            is_sent = result.status == NotificationDeliveryStatus.SENT.value
            return await recorder.record(
                status=result.status,
                provider=result.provider,
                template_key=_SANDBOX_FREEFORM_TEMPLATE_KEY,
                phone=sandbox_recipient,
                provider_message_id=result.provider_message_id,
                error_message=result.error_message,
                failure_category=None if is_sent else "provider",
            )

    return await recorder.record(
        status=NotificationDeliveryStatus.SKIPPED_TEMPLATE_MISSING.value,
        provider="disabled",
        template_key=_TEST_TEMPLATE_CODE,
        phone=phone,
        error_message="Onaylı test şablonu henüz yapılandırılmamış.",
    )
