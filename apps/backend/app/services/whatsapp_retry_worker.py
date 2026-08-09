"""Background retry worker for WhatsApp deliveries (Part 6B-3).

No Celery/APScheduler exists in this codebase — every other background job
(deadline reminders, demo sandbox cleanup, finance/capacity checks, time
tracking) is a plain `asyncio.create_task` loop started from `app.main`'s
lifespan (see deadline_scheduler.py). This module follows the same shape:
`start_whatsapp_retry_worker()` returns a cancellable Task, and
`run_retry_batch()` — the actual unit of work — is exposed standalone so
tests can call it directly against a single asyncio event loop without
waiting on the poll interval.

Concurrency: `NotificationDeliveryRepository.claim_batch_for_retry` does the
actual atomic claim (SELECT ... FOR UPDATE SKIP LOCKED + a lease write) in
its own short transaction; every claimed row is then processed in its own
separate session/transaction so a slow or failing provider call for one
delivery never holds a lock other workers/rows are waiting on.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.enums import NotificationDeliveryStatus
from app.models.notification import NotificationDelivery, NotificationEvent
from app.models.user import User
from app.repositories.notification import (
    NotificationDeliveryRepository,
    NotificationPreferenceRepository,
)
from app.repositories.whatsapp_template import WhatsAppTemplateRepository
from app.services.whatsapp_event_catalog import get_event_definition
from app.services.whatsapp_payload_builder import build_variables, map_to_content_variables
from app.services.whatsapp_provider import DisabledWhatsAppProvider, WhatsAppProviderFactory
from app.services.whatsapp_retry_policy import (
    compute_backoff_seconds,
    is_attempt_budget_exhausted,
    is_retryable,
)
from app.services.whatsapp_retry_revalidation import revalidate_before_retry

log = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 30
_BATCH_SIZE = 20


async def run_retry_batch(*, now: datetime | None = None, batch_size: int = _BATCH_SIZE) -> int:
    """Claim and (re)attempt one batch of eligible WhatsApp retries. Each
    claimed delivery is processed and committed independently, isolated by
    its own try/except, so one bad row can't sink the rest of the batch or
    leave a half-updated transaction behind. Returns the number claimed."""
    now = now or datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        delivery_repo = NotificationDeliveryRepository(db)
        claimed = await delivery_repo.claim_batch_for_retry(limit=batch_size, now=now)
        await db.commit()
        claimed_ids = [d.id for d in claimed]

    for delivery_id in claimed_ids:
        async with AsyncSessionLocal() as db:
            try:
                await _process_one_retry(db, delivery_id, now)
                await db.commit()
            except Exception:
                await db.rollback()
                log.exception(
                    "WhatsApp retry attempt failed unexpectedly for delivery %s", delivery_id
                )
    return len(claimed_ids)


async def _process_one_retry(
    db: AsyncSession, delivery_id: uuid.UUID, now: datetime
) -> None:
    delivery_repo = NotificationDeliveryRepository(db)
    delivery = await db.get(NotificationDelivery, delivery_id)
    if delivery is None:
        return

    event = await db.get(NotificationEvent, delivery.event_id)
    user = await db.get(User, delivery.recipient_user_id) if delivery.recipient_user_id else None
    if event is None or user is None:
        # The domain occurrence or recipient no longer exists — nothing
        # left to retry.
        await delivery_repo.finalize_retry_as(
            delivery,
            status=NotificationDeliveryStatus.CANCELLED.value,
            reason="Event veya alıcı artık mevcut değil.",
            now=now,
        )
        return

    pref_repo = NotificationPreferenceRepository(db)
    pref = await pref_repo.get_or_create(user.id)

    outcome = await revalidate_before_retry(db, delivery, event=event, user=user, pref=pref)
    if outcome is not None:
        await delivery_repo.finalize_retry_as(
            delivery, status=outcome.status, reason=outcome.reason, now=now
        )
        return

    definition = get_event_definition(event.event_type)
    assert definition is not None  # revalidate_before_retry already checked this

    template_repo = WhatsAppTemplateRepository(db)
    template = await template_repo.get_approved(
        definition.template_key, locale=definition.locale_fallback, provider="twilio"
    )
    if template is None:
        # Revalidation checked this moments ago — a genuine TOCTOU loss is
        # rare but must fail closed the same way, not fall back to freeform.
        await delivery_repo.finalize_retry_as(
            delivery,
            status=NotificationDeliveryStatus.SKIPPED_TEMPLATE_MISSING.value,
            reason="Onaylı WhatsApp şablonu artık yok.",
            now=now,
        )
        return

    from app.services.phone_utils import mask_phone_e164, normalize_e164

    phone = normalize_e164(user.phone_number) if user.phone_number else None
    if phone is None:  # pragma: no cover - revalidation already checked this
        await delivery_repo.finalize_retry_as(
            delivery,
            status=NotificationDeliveryStatus.SKIPPED_NO_PHONE.value,
            reason="Telefon numarası artık geçersiz.",
            now=now,
        )
        return

    actor_user = await db.get(User, event.actor_user_id) if event.actor_user_id else None
    variables = build_variables(event, user, actor_user)
    content_variables = map_to_content_variables(template, variables)

    wa_provider = await WhatsAppProviderFactory.get_provider(db)
    if isinstance(wa_provider, DisabledWhatsAppProvider):
        await delivery_repo.finalize_retry_as(
            delivery,
            status=NotificationDeliveryStatus.NOT_CONFIGURED.value,
            reason="WhatsApp sağlayıcısı yapılandırılmamış.",
            now=now,
        )
        return

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

    if result_status == NotificationDeliveryStatus.SENT.value:
        await delivery_repo.record_retry_success(
            delivery, provider=result_provider, provider_message_id=result_msg_id, now=now
        )
        delivery.recipient_phone_masked = mask_phone_e164(phone)
        delivery.template_revision = template.revision
        delivery.template_content_sid = template.content_sid
        db.add(delivery)
        return

    next_attempt_count = delivery.attempt_count + 1
    if is_retryable(result_category) and not is_attempt_budget_exhausted(next_attempt_count):
        delay = compute_backoff_seconds(next_attempt_count)
        await delivery_repo.schedule_next_retry(
            delivery,
            next_retry_at=now + timedelta(seconds=delay),
            error_message=result_error,
            failure_category=result_category,
            now=now,
        )
    else:
        await delivery_repo.exhaust_retry(
            delivery, error_message=result_error, failure_category=result_category, now=now
        )


async def _scheduler_loop() -> None:
    while True:
        try:
            await run_retry_batch()
        except Exception:
            log.exception("Unexpected error in WhatsApp retry worker")
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)


def start_whatsapp_retry_worker() -> asyncio.Task[None]:
    """Schedule the WhatsApp retry loop as a background asyncio task."""
    return asyncio.create_task(_scheduler_loop(), name="whatsapp_retry_worker")


__all__ = ["run_retry_batch", "start_whatsapp_retry_worker"]
