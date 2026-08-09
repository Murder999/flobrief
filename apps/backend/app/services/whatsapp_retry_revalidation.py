"""Retry-time revalidation for WhatsApp deliveries (Part 6B-3).

Before the retry worker re-attempts a send, it must re-check every gate the
original dispatch already checked once — the world may have moved on since
the first attempt failed: the user may have opted out, the per-event
preference may have been turned off, the phone may no longer normalize, the
role may no longer be eligible, the template may have been disabled or
changed shape, or the underlying business fact (brief, invoice) may have
resolved itself, making the reminder meaningless. This is the single place
that logic lives; whatsapp_retry_worker.py is the only caller.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agency import Agency
from app.models.brief import Brief
from app.models.client_invoice import ClientInvoice
from app.models.enums import (
    BriefStatus,
    ClientInvoiceStatus,
    NotificationDeliveryStatus,
    NotificationEventType,
)
from app.models.notification import NotificationDelivery, NotificationEvent, NotificationPreference
from app.models.user import User
from app.repositories.notification import NotificationEventPreferenceRepository
from app.repositories.whatsapp_template import WhatsAppTemplateRepository
from app.services.phone_utils import normalize_e164
from app.services.whatsapp_event_catalog import get_event_definition
from app.services.whatsapp_provider import DisabledWhatsAppProvider, WhatsAppProviderFactory
from app.services.whatsapp_recipient_gate import is_whatsapp_role_eligible

# Brief statuses for which a due-soon/overdue reminder is no longer
# meaningful — mirrors deadline_scheduler._REMINDER_EXCLUDED_STATUSES.
_REMINDER_RESOLVED_BRIEF_STATUSES = frozenset(
    {
        BriefStatus.ARCHIVED.value,
        BriefStatus.APPROVED.value,
        BriefStatus.COMPLETED.value,
        BriefStatus.REJECTED.value,
    }
)

_REMINDER_RESOLVED_INVOICE_STATUSES = frozenset(
    {
        ClientInvoiceStatus.PAID.value,
        ClientInvoiceStatus.CANCELLED.value,
    }
)


@dataclass(frozen=True)
class RevalidationOutcome:
    """A non-None return from `revalidate_before_retry` means "do not call
    the provider" — `status`/`reason` are what the retry should be
    finalized with instead."""

    status: str
    reason: str


async def _safe_get(db: AsyncSession, model: type, raw_id: object) -> object | None:
    if not raw_id:
        return None
    try:
        pk = uuid.UUID(str(raw_id))
    except (ValueError, TypeError):
        return None
    return await db.get(model, pk)


async def _revalidate_business_context(
    db: AsyncSession, event: NotificationEvent
) -> RevalidationOutcome | None:
    payload = event.payload or {}

    reminder_events = (
        NotificationEventType.CALENDAR_ITEM_DUE.value,
        NotificationEventType.BRIEF_OVERDUE.value,
    )
    if event.event_type in reminder_events:
        raw_id = payload.get("brief_id")
        brief = await _safe_get(db, Brief, raw_id)
        if raw_id and (brief is None or brief.status in _REMINDER_RESOLVED_BRIEF_STATUSES):
            return RevalidationOutcome(
                NotificationDeliveryStatus.EXPIRED.value,
                "Brief artık hatırlatma gerektirmiyor "
                "(tamamlandı/onaylandı/arşivlendi/reddedildi).",
            )

    invoice_reminder_events = (
        NotificationEventType.INVOICE_DUE_SOON.value,
        NotificationEventType.INVOICE_OVERDUE.value,
    )
    if event.event_type in invoice_reminder_events:
        raw_id = payload.get("invoice_id")
        invoice = await _safe_get(db, ClientInvoice, raw_id)
        if raw_id and (invoice is None or invoice.status in _REMINDER_RESOLVED_INVOICE_STATUSES):
            return RevalidationOutcome(
                NotificationDeliveryStatus.EXPIRED.value,
                "Fatura artık hatırlatma gerektirmiyor (ödendi/iptal edildi).",
            )

    return None


async def revalidate_before_retry(
    db: AsyncSession,
    delivery: NotificationDelivery,
    *,
    event: NotificationEvent,
    user: User,
    pref: NotificationPreference,
) -> RevalidationOutcome | None:
    """Returns None if the retry should proceed to an actual provider call,
    otherwise a `RevalidationOutcome` describing why it must not."""
    definition = get_event_definition(event.event_type)
    if definition is None:
        return RevalidationOutcome(
            NotificationDeliveryStatus.CANCELLED.value, "Event artık WhatsApp kataloğunda değil."
        )

    if event.agency_id is not None:
        is_demo = bool(
            await db.scalar(
                select(Agency.is_demo).where(
                    Agency.id == event.agency_id, Agency.deleted_at.is_(None)
                )
            )
        )
        if is_demo:
            return RevalidationOutcome(
                NotificationDeliveryStatus.SKIPPED_DEMO_TENANT.value, "Demo tenant."
            )

    if not pref.whatsapp_enabled or not user.whatsapp_opt_in:
        return RevalidationOutcome(
            NotificationDeliveryStatus.SKIPPED_NO_CONSENT.value,
            "Kullanıcının WhatsApp bildirim onayı artık yok.",
        )

    event_pref_repo = NotificationEventPreferenceRepository(db)
    event_prefs = await event_pref_repo.list_for_user(user.id)
    event_pref = event_prefs.get(event.event_type)
    if event_pref is not None and not event_pref.whatsapp_enabled:
        return RevalidationOutcome(
            NotificationDeliveryStatus.SKIPPED_EVENT_DISABLED.value,
            "Kullanıcı bu event için WhatsApp bildirimini kapattı.",
        )

    phone = normalize_e164(user.phone_number) if user.phone_number else None
    if phone is None:
        return RevalidationOutcome(
            NotificationDeliveryStatus.SKIPPED_NO_PHONE.value, "Telefon numarası artık geçersiz."
        )

    if not await is_whatsapp_role_eligible(db, event, user):
        return RevalidationOutcome(
            NotificationDeliveryStatus.SKIPPED_ROLE.value,
            "Kullanıcı artık bu event için role-eligible değil.",
        )

    template_repo = WhatsAppTemplateRepository(db)
    template = await template_repo.get_approved(
        definition.template_key, locale=definition.locale_fallback, provider="twilio"
    )
    if template is None:
        return RevalidationOutcome(
            NotificationDeliveryStatus.SKIPPED_TEMPLATE_MISSING.value,
            "Onaylı WhatsApp şablonu artık yok.",
        )
    if delivery.template_revision is not None and template.revision != delivery.template_revision:
        return RevalidationOutcome(
            NotificationDeliveryStatus.SKIPPED_TEMPLATE_MISSING.value,
            "Şablon bu delivery oluşturulduğundan beri değişti; stale gönderim engellendi.",
        )

    wa_provider = await WhatsAppProviderFactory.get_provider(db)
    if isinstance(wa_provider, DisabledWhatsAppProvider):
        return RevalidationOutcome(
            NotificationDeliveryStatus.NOT_CONFIGURED.value,
            "WhatsApp sağlayıcısı yapılandırılmamış.",
        )

    business_outcome = await _revalidate_business_context(db, event)
    if business_outcome is not None:
        return business_outcome

    return None


__all__ = ["RevalidationOutcome", "revalidate_before_retry"]
