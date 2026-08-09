"""NotificationDispatcher: fan-out events to in-app notifications, email, and WhatsApp."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.services.whatsapp_provider import WhatsAppProvider

from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand_member import BrandMember
from app.models.enums import NotificationChannel, NotificationDeliveryStatus, NotificationEventType
from app.models.notification import NotificationEvent, NotificationPreference
from app.models.user import User
from app.repositories.notification import (
    NotificationDeliveryRepository,
    NotificationEventPreferenceRepository,
    NotificationEventRepository,
    NotificationPreferenceRepository,
    NotificationRepository,
)
from app.repositories.whatsapp_template import WhatsAppTemplateRepository
from app.services import email_service
from app.services.notification_dedupe import build_whatsapp_idempotency_key
from app.services.notification_realtime import queue_notification_signal
from app.services.phone_utils import mask_phone_e164, normalize_e164
from app.services.resend_email_provider import (
    DisabledEmailProvider,
    EmailDeliveryResult,
    EmailProviderFactory,
    ResendEmailProvider,
)
from app.services.url_builder import url_builder
from app.services.whatsapp_event_catalog import get_event_definition
from app.services.whatsapp_payload_builder import build_variables, map_to_content_variables
from app.services.whatsapp_recipient_gate import is_whatsapp_role_eligible
from app.services.whatsapp_retry_policy import (
    compute_backoff_seconds,
    is_attempt_budget_exhausted,
    is_retryable,
)

log = logging.getLogger(__name__)

_EVENT_TITLES: dict[str, str] = {
    NotificationEventType.BRIEF_CREATED.value: "Yeni brief oluşturuldu",
    NotificationEventType.BRIEF_UPDATED.value: "Brief güncellendi",
    NotificationEventType.BRIEF_SUBMITTED.value: "Brief onaya gönderildi",
    NotificationEventType.BRIEF_REVISION_REQUESTED.value: "Revizyon istendi",
    NotificationEventType.BRIEF_APPROVED.value: "Brief onaylandı",
    NotificationEventType.BRIEF_REQUESTED.value: "Yeni brief talebi",
    NotificationEventType.BRIEF_ACCEPTED.value: "Brief kabul edildi",
    NotificationEventType.BRIEF_PRODUCTION_STARTED.value: "Brief üretime alındı",
    NotificationEventType.BRIEF_READY_FOR_REVIEW.value: "Brief incelemeye hazır",
    NotificationEventType.BRIEF_COMPLETED.value: "Brief tamamlandı",
    NotificationEventType.COMMENT_ADDED.value: "Yeni yorum",
    NotificationEventType.FILE_UPLOADED.value: "Dosya yüklendi",
    NotificationEventType.CALENDAR_ITEM_CREATED.value: "Yeni takvim içeriği",
    NotificationEventType.CALENDAR_ITEM_DUE.value: "İçerik teslim tarihi yaklaşıyor",
    NotificationEventType.CALENDAR_ITEM_PUBLISHED.value: "İçerik yayınlandı",
    NotificationEventType.USER_INVITED.value: "Yeni davet gönderildi",
    NotificationEventType.SUBSCRIPTION_PAYMENT_FAILED.value: "Ödeme başarısız",
    NotificationEventType.SUBSCRIPTION_CHANGED.value: "Abonelik değişti",
    NotificationEventType.DELIVERABLE_SUBMITTED.value: "Yeni teslimat inceleme bekliyor",
    NotificationEventType.DELIVERABLE_APPROVED.value: "Teslimat onaylandı",
    NotificationEventType.DELIVERABLE_REVISION_REQUESTED.value: "Teslimat revizyonu istendi",
    NotificationEventType.PUBLIC_APPROVAL_APPROVED.value: "Kamuya açık onay verildi",
    NotificationEventType.PUBLIC_APPROVAL_REVISION_REQUESTED.value: "Kamuya açık revizyon istendi",
    NotificationEventType.MILESTONE_ASSIGNED.value: "Görev atandı",
    NotificationEventType.ANNOTATION_CREATED.value: "Yeni revizyon notu eklendi",
    NotificationEventType.ANNOTATION_RESOLVED.value: "Revizyon notu çözüldü",
    NotificationEventType.ANNOTATION_REPLIED.value: "Revizyon notuna yanıt geldi",
    NotificationEventType.ANNOTATION_REOPENED.value: "Revizyon notu yeniden açıldı",
    NotificationEventType.MENTIONED_IN_COMMENT.value: "Bir yorumda etiketlendiniz",
    NotificationEventType.MENTIONED_IN_ANNOTATION.value: "Bir revizyon notunda etiketlendiniz",
    NotificationEventType.TIME_ENTRY_LONG_RUNNING.value: "Uzun süredir çalışan zamanlayıcı",
    NotificationEventType.TIME_ENTRY_STILL_RUNNING_EOD.value: (
        "Gün sonunda hâlâ çalışan zamanlayıcı"
    ),
    NotificationEventType.TIMESHEET_MISSING.value: "Eksik zaman kaydı",
    NotificationEventType.TIME_ENTRY_APPROVAL_PENDING.value: "Onay bekleyen zaman kayıtları",
    NotificationEventType.BRIEF_ESTIMATE_OVERRUN.value: "Tahmini süre aşıldı",
    NotificationEventType.INVOICE_SENT.value: "Fatura gönderildi",
    NotificationEventType.INVOICE_APPROVAL_PENDING.value: "Fatura onay bekliyor",
    NotificationEventType.INVOICE_SEND_FAILED.value: "Fatura gönderimi başarısız oldu",
    NotificationEventType.INVOICE_OVERDUE.value: "Fatura vadesi geçti",
    NotificationEventType.TIME_OFF_APPROVED.value: "İzin talebiniz onaylandı",
    NotificationEventType.TIME_OFF_REJECTED.value: "İzin talebiniz reddedildi",
    NotificationEventType.CAPACITY_OVER_THRESHOLD.value: "Kapasite eşiği aşıldı",
    NotificationEventType.COMMERCIAL_TERMS_EXPIRING.value: "Ticari koşul süresi doluyor",
    NotificationEventType.RETAINER_OVERAGE.value: "Retainer kullanım aşımı",
    NotificationEventType.CRITICAL_WORK_UNASSIGNED.value: "Kritik iş atanmamış",
}


class NotificationDispatcher:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._event_repo = NotificationEventRepository(db)
        self._notif_repo = NotificationRepository(db)
        self._pref_repo = NotificationPreferenceRepository(db)
        self._delivery_repo = NotificationDeliveryRepository(db)
        self._wa_template_repo = WhatsAppTemplateRepository(db)

    async def emit(
        self,
        event_type: str,
        payload: dict,
        agency_id: uuid.UUID | None = None,
        brand_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        recipient_ids: list[uuid.UUID] | None = None,
    ) -> NotificationEvent:
        """Create event record and dispatch.

        recipient_ids: explicit list of user IDs to notify.
        When None, falls back to all active agency members.
        """
        event = await self._event_repo.create(
            event_type=event_type,
            payload=payload,
            agency_id=agency_id,
            brand_id=brand_id,
            actor_user_id=actor_user_id,
        )
        await self._dispatch(event, recipient_ids=recipient_ids)
        return event

    async def _dispatch(
        self,
        event: NotificationEvent,
        recipient_ids: list[uuid.UUID] | None = None,
    ) -> None:
        demo_sandbox = False
        if event.agency_id is not None:
            demo_sandbox = bool(
                await self._db.scalar(
                    select(Agency.is_demo).where(
                        Agency.id == event.agency_id,
                        Agency.deleted_at.is_(None),
                    )
                )
            )

        recipients = (
            await self._get_users_by_ids(recipient_ids)
            if recipient_ids is not None
            else await self._get_agency_members(event)
        )

        title = _EVENT_TITLES.get(event.event_type, event.event_type)
        body = event.payload.get("summary", title)

        from app.services.whatsapp_provider import DisabledWhatsAppProvider, WhatsAppProviderFactory

        try:
            wa_provider = await WhatsAppProviderFactory.get_provider(self._db)
        except Exception:
            wa_provider = DisabledWhatsAppProvider()

        try:
            email_provider: (
                ResendEmailProvider | DisabledEmailProvider
            ) = await EmailProviderFactory.get_provider(self._db)
        except Exception:
            email_provider = DisabledEmailProvider()

        actor_user: User | None = None
        if event.actor_user_id is not None:
            actor_matches = await self._get_users_by_ids([event.actor_user_id])
            actor_user = actor_matches[0] if actor_matches else None

        for user in recipients:
            if user.id == event.actor_user_id:
                continue

            pref = await self._pref_repo.get_or_create(user.id)

            # ── In-app ─────────────────────────────────────────────────────
            if pref.in_app_enabled:
                notif = await self._notif_repo.create(
                    user_id=user.id,
                    event_id=event.id,
                    title=title,
                    body=body,
                    event_type=event.event_type,
                    agency_id=event.agency_id,
                    brand_id=event.brand_id,
                )
                await self._delivery_repo.create(
                    event_id=event.id,
                    channel=NotificationChannel.IN_APP.value,
                    status=NotificationDeliveryStatus.SENT.value,
                    provider="in_app",
                    notification_id=notif.id,
                    sent_at=datetime.now(UTC),
                )
                queue_notification_signal(
                    self._db,
                    user_id=user.id,
                    agency_id=event.agency_id,
                    brand_id=event.brand_id,
                )

            # ── Email ───────────────────────────────────────────────────────
            if demo_sandbox and pref.email_enabled and user.email:
                await self._delivery_repo.create(
                    event_id=event.id,
                    channel=NotificationChannel.EMAIL.value,
                    status=NotificationDeliveryStatus.SKIPPED.value,
                    provider="demo_sandbox",
                    error_message="External delivery disabled for demo sandbox",
                    recipient_email=user.email,
                )
            elif pref.email_enabled and user.email:
                email_result = await self._deliver_event_email(
                    event, user, title, body, email_provider
                )
                await self._delivery_repo.create(
                    event_id=event.id,
                    channel=NotificationChannel.EMAIL.value,
                    status=email_result.status,
                    provider=email_result.provider,
                    provider_message_id=email_result.provider_message_id,
                    error_message=email_result.error_message,
                    recipient_email=user.email,
                    sent_at=(
                        datetime.now(UTC)
                        if email_result.status == NotificationDeliveryStatus.SENT.value
                        else None
                    ),
                )

            # ── WhatsApp ────────────────────────────────────────────────────
            # Never allowed to affect the domain transaction or the other
            # channels above — any unexpected failure here is caught, logged,
            # and recorded as a normal FAILED delivery row, nothing raises.
            try:
                await self._dispatch_whatsapp(
                    event=event,
                    user=user,
                    pref=pref,
                    demo_sandbox=demo_sandbox,
                    wa_provider=wa_provider,
                    actor_user=actor_user,
                )
            except Exception:
                log.exception(
                    "WhatsApp dispatch failed for event %s recipient %s", event.id, user.id
                )

        await self._event_repo.mark_processed(event)

    async def _dispatch_whatsapp(
        self,
        *,
        event: NotificationEvent,
        user: User,
        pref: NotificationPreference,
        demo_sandbox: bool,
        wa_provider: WhatsAppProvider,
        actor_user: User | None,
    ) -> None:
        """Route one event to one recipient's WhatsApp, gated end-to-end by
        the approved-template registry (never a freeform auto-send — that
        path is reserved for the dev-only Sandbox test-send flow, Part 6A).

        Order: catalog membership first (cheap, in-memory — a non-WhatsApp
        event needs no delivery row at all), then an atomic reservation of
        the (domain occurrence, recipient, channel) idempotency slot, then
        demo tenant / consent / phone / role gates, then the approved-
        template lookup, then the provider call. The reservation happens
        via `NotificationDeliveryRepository.reserve()` (INSERT ... ON
        CONFLICT DO NOTHING against a DB-unique idempotency_key) *before*
        any provider call, so two concurrent dispatches for the same domain
        occurrence — two NotificationEvent rows for the same real action, or
        two racing workers — can never both reach the provider: whichever
        loses the race gets None back and returns immediately. Every branch
        past the reservation updates that same row and returns — never
        raises past this method.
        """
        from app.services.whatsapp_provider import DisabledWhatsAppProvider

        definition = get_event_definition(event.event_type)
        if definition is None:
            # Not a WhatsApp-catalog event (e.g. a purely in-app/email event
            # type) — nothing to do, no delivery row needed.
            return

        # Deterministic key derived from the domain occurrence (entity id +
        # version/revision/reminder-day where applicable), not from
        # NotificationEvent.id — so two NotificationEvent rows created for
        # the same real action collapse to one delivery. See
        # notification_dedupe.py for the full rationale.
        idempotency_key = build_whatsapp_idempotency_key(event, user.id)
        delivery = await self._delivery_repo.reserve(
            event_id=event.id,
            channel=NotificationChannel.WHATSAPP.value,
            status=NotificationDeliveryStatus.PROCESSING.value,
            idempotency_key=idempotency_key,
            recipient_user_id=user.id,
            agency_id=event.agency_id,
        )
        if delivery is None:
            # Another concurrent dispatch already claimed this exact
            # (domain occurrence, recipient, channel) slot — nothing left
            # for this call to do.
            return

        if demo_sandbox:
            await self._delivery_repo.update_result(
                delivery,
                status=NotificationDeliveryStatus.SKIPPED_DEMO_TENANT.value,
                provider="disabled",
                error_message="Demo tenant'ta WhatsApp bildirimi gönderilmez.",
                template_key=definition.template_key,
            )
            return

        if not pref.whatsapp_enabled or not user.whatsapp_opt_in:
            await self._delivery_repo.update_result(
                delivery,
                status=NotificationDeliveryStatus.SKIPPED_NO_CONSENT.value,
                provider="disabled",
                error_message="Kullanıcının WhatsApp bildirim onayı yok.",
                template_key=definition.template_key,
            )
            return

        event_pref_repo = NotificationEventPreferenceRepository(self._db)
        event_prefs = await event_pref_repo.list_for_user(user.id)
        event_pref = event_prefs.get(event.event_type)
        if event_pref is not None and not event_pref.whatsapp_enabled:
            await self._delivery_repo.update_result(
                delivery,
                status=NotificationDeliveryStatus.SKIPPED_EVENT_DISABLED.value,
                provider="disabled",
                error_message="Kullanıcı bu event için WhatsApp bildirimini kapattı.",
                template_key=definition.template_key,
            )
            return

        phone = normalize_e164(user.phone_number) if user.phone_number else None
        if phone is None:
            await self._delivery_repo.update_result(
                delivery,
                status=NotificationDeliveryStatus.SKIPPED_NO_PHONE.value,
                provider="disabled",
                error_message="Kayıtlı/geçerli bir telefon numarası yok.",
                template_key=definition.template_key,
            )
            return

        recipient_phone_masked = mask_phone_e164(phone)

        if not await is_whatsapp_role_eligible(self._db, event, user):
            await self._delivery_repo.update_result(
                delivery,
                status=NotificationDeliveryStatus.SKIPPED.value,
                provider="disabled",
                error_message="Bu event WhatsApp üzerinden yalnızca yetkili role gider.",
                template_key=definition.template_key,
                recipient_phone_masked=recipient_phone_masked,
            )
            return

        template = await self._wa_template_repo.get_approved(
            definition.template_key,
            locale=definition.locale_fallback,
            provider="twilio",
        )
        if template is None:
            await self._delivery_repo.update_result(
                delivery,
                status=NotificationDeliveryStatus.SKIPPED_TEMPLATE_MISSING.value,
                provider=wa_provider.get_provider_name(),
                error_message="Onaylı WhatsApp şablonu bulunamadı.",
                template_key=definition.template_key,
                recipient_phone_masked=recipient_phone_masked,
            )
            return

        if isinstance(wa_provider, DisabledWhatsAppProvider):
            await self._delivery_repo.update_result(
                delivery,
                status=NotificationDeliveryStatus.NOT_CONFIGURED.value,
                provider=wa_provider.get_provider_name(),
                error_message="WhatsApp sağlayıcısı yapılandırılmamış.",
                template_key=definition.template_key,
                recipient_phone_masked=recipient_phone_masked,
            )
            return

        variables = build_variables(event, user, actor_user)
        content_variables = map_to_content_variables(template, variables)

        try:
            result = wa_provider.send_template_message(
                phone, template.content_sid or "", content_variables
            )
        except Exception as exc:
            result_status = NotificationDeliveryStatus.FAILED.value
            result_provider = wa_provider.get_provider_name()
            result_msg_id = None
            result_error = f"Unexpected error: {type(exc).__name__}"
            result_category: str | None = None
        else:
            result_status = result.status
            result_provider = result.provider
            result_msg_id = result.provider_message_id
            result_error = result.error_message
            result_category = result.failure_category

        now = datetime.now(UTC)
        # This is delivery's first send attempt (attempt_count is still 0
        # here — record_send_attempt increments it below), so the budget
        # check below looks one attempt ahead.
        next_retry_at = None
        if (
            result_status == NotificationDeliveryStatus.FAILED.value
            and is_retryable(result_category)
            and not is_attempt_budget_exhausted(delivery.attempt_count + 1)
        ):
            delay = compute_backoff_seconds(delivery.attempt_count + 1)
            next_retry_at = now + timedelta(seconds=delay)

        await self._delivery_repo.record_send_attempt(
            delivery,
            status=result_status,
            provider=result_provider,
            provider_message_id=result_msg_id,
            error_message=result_error,
            failure_category=result_category,
            template_key=definition.template_key,
            recipient_phone_masked=recipient_phone_masked,
            template_revision=template.revision,
            template_content_sid=template.content_sid,
            sent_at=now if result_status == NotificationDeliveryStatus.SENT.value else None,
            next_retry_at=next_retry_at,
            now=now,
        )

    # ── Email routing ─────────────────────────────────────────────────────────

    async def _deliver_event_email(
        self,
        event: NotificationEvent,
        user: User,
        title: str,
        body: str,
        email_provider: ResendEmailProvider | DisabledEmailProvider,
    ) -> EmailDeliveryResult:
        """Deliver through Resend; return not_configured when email is disabled."""
        if email_provider.is_active():
            html = self._build_event_email_html(event, user, title, body)
            subject = self._build_event_email_subject(event, title)
            if html is None:
                return EmailDeliveryResult(
                    status=NotificationDeliveryStatus.SKIPPED.value,
                    provider=email_provider.get_provider_name(),
                    provider_message_id=None,
                    error_message="Bu event tipi için email şablonu yok",
                )
            return await email_provider.send(
                to_email=user.email,
                subject=subject,
                html=html,
            )
        return EmailDeliveryResult(
            status=NotificationDeliveryStatus.NOT_CONFIGURED.value,
            provider="disabled",
            provider_message_id=None,
            error_message="Email provider not configured",
        )

    def _build_event_email_html(
        self,
        event: NotificationEvent,
        user: User,
        title: str,
        body: str,
    ) -> str | None:
        p = event.payload
        brief_id_str = p.get("brief_id")
        brief_title = p.get("brief_title", "Brief")
        agency_name = p.get("agency_name", "Ajans")
        et = event.event_type

        try:
            if et == NotificationEventType.BRIEF_SUBMITTED.value and brief_id_str:
                brief_url = url_builder.brief_detail(uuid.UUID(brief_id_str))
                return email_service.build_brief_approval_request_html(
                    recipient_name=user.full_name,
                    agency_name=agency_name,
                    brief_title=brief_title,
                    approval_url=brief_url,
                )
            if et == NotificationEventType.BRIEF_REVISION_REQUESTED.value and brief_id_str:
                brief_url = url_builder.brief_detail(uuid.UUID(brief_id_str))
                return email_service.build_brief_revision_requested_html(
                    recipient_name=user.full_name,
                    brief_title=brief_title,
                    revision_note=p.get("reason", "Revizyon talep edildi."),
                    brief_url=brief_url,
                )
            if et == NotificationEventType.BRIEF_APPROVED.value and brief_id_str:
                brief_url = url_builder.brief_detail(uuid.UUID(brief_id_str))
                return email_service.build_brief_approved_html(
                    recipient_name=user.full_name,
                    brief_title=brief_title,
                    brief_url=brief_url,
                )
            deliverable_title = p.get("deliverable_title", "Teslimat")
            if et == NotificationEventType.DELIVERABLE_SUBMITTED.value and brief_id_str:
                brief_url = url_builder.brief_detail(uuid.UUID(brief_id_str))
                return email_service.build_generic_notification_html(
                    recipient_name=user.full_name,
                    title=f"Yeni teslimat: {deliverable_title}",
                    body=(
                        f"{agency_name} — '{brief_title}' briefi için yeni bir teslimat "
                        f"incelemenizi bekliyor: {deliverable_title}"
                    ),
                    action_url=brief_url,
                    action_label="Teslimatı İncele",
                )
            if et == NotificationEventType.DELIVERABLE_APPROVED.value and brief_id_str:
                brief_url = url_builder.brief_detail(uuid.UUID(brief_id_str))
                return email_service.build_generic_notification_html(
                    recipient_name=user.full_name,
                    title=f"Teslimat onaylandı: {deliverable_title}",
                    body=(
                        f"'{brief_title}' briefindeki '{deliverable_title}' teslimati "
                        f"{p.get('brand_name', 'marka')} tarafından onaylandı."
                    ),
                    action_url=brief_url,
                    action_label="Brief'e Git",
                )
            if et == NotificationEventType.DELIVERABLE_REVISION_REQUESTED.value and brief_id_str:
                brief_url = url_builder.brief_detail(uuid.UUID(brief_id_str))
                return email_service.build_generic_notification_html(
                    recipient_name=user.full_name,
                    title=f"Revizyon istendi: {deliverable_title}",
                    body=(
                        f"'{deliverable_title}' teslimati için revizyon talep edildi. "
                        f"Neden: {p.get('reason', '')[:300]}"
                    ),
                    action_url=brief_url,
                    action_label="Revizyon Detayı",
                )
            if et == NotificationEventType.MILESTONE_ASSIGNED.value and brief_id_str:
                brief_url = url_builder.brief_detail(uuid.UUID(brief_id_str))
                return email_service.build_generic_notification_html(
                    recipient_name=user.full_name,
                    title=f"Görev atandı: {p.get('task_title', 'Görev')}",
                    body=(
                        f"'{p.get('task_title', 'Yeni görev')}' görevi size atandı. "
                        f"Brief: {brief_title}"
                    ),
                    action_url=brief_url,
                    action_label="Göreve Git",
                )
            if et in (
                NotificationEventType.BRIEF_CREATED.value,
                NotificationEventType.BRIEF_REQUESTED.value,
                NotificationEventType.BRIEF_ACCEPTED.value,
                NotificationEventType.BRIEF_PRODUCTION_STARTED.value,
                NotificationEventType.BRIEF_READY_FOR_REVIEW.value,
                NotificationEventType.BRIEF_COMPLETED.value,
                NotificationEventType.COMMENT_ADDED.value,
                NotificationEventType.FILE_UPLOADED.value,
                NotificationEventType.CALENDAR_ITEM_DUE.value,
                NotificationEventType.MENTIONED_IN_COMMENT.value,
                NotificationEventType.MENTIONED_IN_ANNOTATION.value,
            ):
                brief_url = (
                    url_builder.brief_detail(uuid.UUID(brief_id_str))
                    if brief_id_str
                    else url_builder.notification_preferences()
                )
                return email_service.build_generic_notification_html(
                    recipient_name=user.full_name,
                    title=title,
                    body=body,
                    action_url=brief_url,
                )
        except Exception:
            return None
        return None

    def _build_event_email_subject(self, event: NotificationEvent, title: str) -> str:
        p = event.payload
        brief_title = p.get("brief_title", "")
        deliverable_title = p.get("deliverable_title", "")
        et = event.event_type

        if et == NotificationEventType.BRIEF_SUBMITTED.value:
            return f"Flobrief — Onay Bekleniyor: {brief_title}"
        if et == NotificationEventType.BRIEF_REVISION_REQUESTED.value:
            return f"Flobrief — Revizyon İstendi: {brief_title}"
        if et == NotificationEventType.BRIEF_APPROVED.value:
            return f"Flobrief — Onaylandı: {brief_title}"
        if et == NotificationEventType.BRIEF_ACCEPTED.value:
            return f"Flobrief — Brief Kabul Edildi: {brief_title}"
        if et == NotificationEventType.BRIEF_READY_FOR_REVIEW.value:
            return f"Flobrief — İncelemenizi Bekliyor: {brief_title}"
        if et == NotificationEventType.DELIVERABLE_SUBMITTED.value:
            return f"Flobrief — Yeni Teslimat: {deliverable_title or brief_title}"
        if et == NotificationEventType.DELIVERABLE_APPROVED.value:
            return f"Flobrief — Teslimat Onaylandı: {deliverable_title or brief_title}"
        if et == NotificationEventType.DELIVERABLE_REVISION_REQUESTED.value:
            return f"Flobrief — Teslimat Revizyonu: {deliverable_title or brief_title}"
        if et == NotificationEventType.MILESTONE_ASSIGNED.value:
            return f"Flobrief — Görev Atandı: {p.get('task_title', 'Yeni Görev')}"
        if et in (
            NotificationEventType.MENTIONED_IN_COMMENT.value,
            NotificationEventType.MENTIONED_IN_ANNOTATION.value,
        ):
            return f"Flobrief — {p.get('actor_name', 'Biri')} sizi etiketledi: {brief_title}"
        return f"Flobrief — {title}"

    async def _send_event_email(
        self, event: NotificationEvent, user: User, title: str, body: str
    ) -> bool:
        """Route event to the correct email template. Returns True on success."""
        p = event.payload
        brief_id_str = p.get("brief_id")
        brief_title = p.get("brief_title", "Brief")
        agency_name = p.get("agency_name", "Ajans")

        try:
            et = event.event_type

            if et == NotificationEventType.BRIEF_SUBMITTED.value and brief_id_str:
                brief_url = url_builder.brief_detail(uuid.UUID(brief_id_str))
                await email_service.send_brief_approval_request_email(
                    to_email=user.email,
                    recipient_name=user.full_name,
                    agency_name=agency_name,
                    brief_title=brief_title,
                    approval_url=brief_url,
                )

            elif et == NotificationEventType.BRIEF_REVISION_REQUESTED.value and brief_id_str:
                brief_url = url_builder.brief_detail(uuid.UUID(brief_id_str))
                await email_service.send_brief_revision_requested_email(
                    to_email=user.email,
                    recipient_name=user.full_name,
                    brief_title=brief_title,
                    revision_note=p.get("reason", "Revizyon talep edildi."),
                    brief_url=brief_url,
                )

            elif et == NotificationEventType.BRIEF_APPROVED.value and brief_id_str:
                brief_url = url_builder.brief_detail(uuid.UUID(brief_id_str))
                await email_service.send_brief_approved_email(
                    to_email=user.email,
                    recipient_name=user.full_name,
                    brief_title=brief_title,
                    brief_url=brief_url,
                )

            elif et in (
                NotificationEventType.BRIEF_CREATED.value,
                NotificationEventType.BRIEF_REQUESTED.value,
                NotificationEventType.BRIEF_ACCEPTED.value,
                NotificationEventType.BRIEF_PRODUCTION_STARTED.value,
                NotificationEventType.BRIEF_READY_FOR_REVIEW.value,
                NotificationEventType.BRIEF_COMPLETED.value,
                NotificationEventType.COMMENT_ADDED.value,
                NotificationEventType.FILE_UPLOADED.value,
                NotificationEventType.CALENDAR_ITEM_DUE.value,
                NotificationEventType.DELIVERABLE_SUBMITTED.value,
                NotificationEventType.DELIVERABLE_APPROVED.value,
                NotificationEventType.DELIVERABLE_REVISION_REQUESTED.value,
                NotificationEventType.MILESTONE_ASSIGNED.value,
            ):
                brief_url = (
                    url_builder.brief_detail(uuid.UUID(brief_id_str))
                    if brief_id_str
                    else url_builder.notification_preferences()
                )
                await email_service.send_generic_notification_email(
                    to_email=user.email,
                    recipient_name=user.full_name,
                    title=title,
                    body=body,
                    action_url=brief_url,
                )

            else:
                # Unknown event type — skip email
                return False

        except Exception:
            return False

        return True

    # ── Recipient helpers ─────────────────────────────────────────────────────

    async def get_agency_members(self, agency_id: uuid.UUID) -> list[User]:
        """Fetch active users who are members of an agency."""
        stmt = (
            select(User)
            .join(AgencyMember, AgencyMember.user_id == User.id)
            .where(
                AgencyMember.agency_id == agency_id,
                AgencyMember.deleted_at.is_(None),
                User.deleted_at.is_(None),
                User.is_active.is_(True),
            )
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def _get_agency_members(self, event: NotificationEvent) -> list[User]:
        if event.agency_id is None:
            return []
        return await self.get_agency_members(event.agency_id)

    async def get_brand_members(self, brand_id: uuid.UUID) -> list[User]:
        """Fetch active users who are members of a brand."""
        stmt = (
            select(User)
            .join(BrandMember, BrandMember.user_id == User.id)
            .where(
                BrandMember.brand_id == brand_id,
                BrandMember.deleted_at.is_(None),
                User.deleted_at.is_(None),
                User.is_active.is_(True),
            )
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def _get_users_by_ids(self, user_ids: list[uuid.UUID]) -> list[User]:
        if not user_ids:
            return []
        stmt = select(User).where(
            User.id.in_(user_ids),
            User.deleted_at.is_(None),
            User.is_active.is_(True),
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
