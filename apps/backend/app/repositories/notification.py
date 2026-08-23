from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationChannel
from app.models.notification import (
    Notification,
    NotificationDelivery,
    NotificationEvent,
    NotificationEventPreference,
    NotificationPreference,
)


class NotificationEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        event_type: str,
        payload: dict,
        agency_id: uuid.UUID | None = None,
        brand_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
    ) -> NotificationEvent:
        event = NotificationEvent(
            event_type=event_type,
            payload=payload,
            agency_id=agency_id,
            brand_id=brand_id,
            actor_user_id=actor_user_id,
        )
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def mark_processed(self, event: NotificationEvent) -> None:
        event.processed_at = datetime.now(UTC)
        self.session.add(event)
        await self.session.flush()

    async def get_by_ids(self, event_ids: list[uuid.UUID]) -> dict[uuid.UUID, NotificationEvent]:
        """Bulk-fetch events for a batch of notifications, keyed by id."""
        if not event_ids:
            return {}
        stmt = select(NotificationEvent).where(NotificationEvent.id.in_(event_ids))
        result = await self.session.execute(stmt)
        return {event.id: event for event in result.scalars().all()}


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: uuid.UUID,
        event_id: uuid.UUID,
        title: str,
        body: str,
        event_type: str,
        agency_id: uuid.UUID | None = None,
        brand_id: uuid.UUID | None = None,
    ) -> Notification:
        notif = Notification(
            user_id=user_id,
            event_id=event_id,
            title=title,
            body=body,
            event_type=event_type,
            agency_id=agency_id,
            brand_id=brand_id,
            is_read=False,
        )
        self.session.add(notif)
        await self.session.flush()
        await self.session.refresh(notif)
        return notif

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        agency_id: uuid.UUID | None = None,
        brand_id: uuid.UUID | None = None,
        unread_only: bool = False,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.deleted_at.is_(None),
            )
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if agency_id:
            stmt = stmt.where(Notification.agency_id == agency_id)
        if brand_id:
            stmt = stmt.where(Notification.brand_id == brand_id)
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))
        if not include_archived:
            stmt = stmt.where(Notification.archived_at.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_unread(
        self,
        user_id: uuid.UUID,
        agency_id: uuid.UUID | None = None,
        brand_id: uuid.UUID | None = None,
    ) -> int:
        stmt = select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
            Notification.archived_at.is_(None),
            Notification.deleted_at.is_(None),
        )
        if agency_id:
            stmt = stmt.where(Notification.agency_id == agency_id)
        if brand_id:
            stmt = stmt.where(Notification.brand_id == brand_id)
        result = await self.session.execute(stmt)
        return len(result.scalars().all())

    async def get_by_id(
        self, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> Notification | None:
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
            Notification.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_read(self, notification: Notification) -> None:
        notification.is_read = True
        notification.read_at = datetime.now(UTC)
        self.session.add(notification)
        await self.session.flush()

    async def archive(self, notification: Notification) -> None:
        notification.archived_at = datetime.now(UTC)
        self.session.add(notification)
        await self.session.flush()

    async def mark_all_read(
        self,
        user_id: uuid.UUID,
        agency_id: uuid.UUID | None = None,
        brand_id: uuid.UUID | None = None,
    ) -> int:
        stmt = (
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
                Notification.deleted_at.is_(None),
            )
            .values(is_read=True, read_at=datetime.now(UTC))
        )
        if agency_id:
            stmt = stmt.where(Notification.agency_id == agency_id)
        if brand_id:
            stmt = stmt.where(Notification.brand_id == brand_id)
        result = await self.session.execute(stmt)
        return result.rowcount  # type: ignore[return-value]


class NotificationPreferenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(self, user_id: uuid.UUID) -> NotificationPreference:
        stmt = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        result = await self.session.execute(stmt)
        pref = result.scalar_one_or_none()
        if pref is None:
            pref = NotificationPreference(user_id=user_id)
            self.session.add(pref)
            await self.session.flush()
            await self.session.refresh(pref)
        return pref

    async def update(
        self,
        pref: NotificationPreference,
        email_enabled: bool,
        whatsapp_enabled: bool,
        in_app_enabled: bool,
    ) -> NotificationPreference:
        pref.email_enabled = email_enabled
        pref.whatsapp_enabled = whatsapp_enabled
        pref.in_app_enabled = in_app_enabled
        self.session.add(pref)
        await self.session.flush()
        await self.session.refresh(pref)
        return pref


class NotificationDeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        event_id: uuid.UUID,
        channel: str,
        status: str,
        provider: str,
        notification_id: uuid.UUID | None = None,
        provider_message_id: str | None = None,
        error_message: str | None = None,
        sent_at: datetime | None = None,
        recipient_email: str | None = None,
        recipient_phone_masked: str | None = None,
        recipient_user_id: uuid.UUID | None = None,
        template_key: str | None = None,
        idempotency_key: str | None = None,
        queued_at: datetime | None = None,
        delivered_at: datetime | None = None,
        read_at: datetime | None = None,
        failure_category: str | None = None,
    ) -> NotificationDelivery:
        delivery = NotificationDelivery(
            event_id=event_id,
            channel=channel,
            status=status,
            provider=provider,
            notification_id=notification_id,
            provider_message_id=provider_message_id,
            error_message=error_message,
            sent_at=sent_at,
            recipient_email=recipient_email,
            recipient_phone_masked=recipient_phone_masked,
            recipient_user_id=recipient_user_id,
            template_key=template_key,
            idempotency_key=idempotency_key,
            queued_at=queued_at,
            delivered_at=delivered_at,
            read_at=read_at,
            failure_category=failure_category,
        )
        self.session.add(delivery)
        await self.session.flush()
        await self.session.refresh(delivery)
        return delivery

    async def get_by_idempotency_key(self, idempotency_key: str) -> NotificationDelivery | None:
        """Look up an existing delivery by its deterministic idempotency key
        so callers can skip re-sending before creating a new row."""
        stmt = select(NotificationDelivery).where(
            NotificationDelivery.idempotency_key == idempotency_key
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def reserve(
        self,
        event_id: uuid.UUID,
        channel: str,
        status: str,
        idempotency_key: str,
        recipient_user_id: uuid.UUID | None = None,
        agency_id: uuid.UUID | None = None,
    ) -> NotificationDelivery | None:
        """Atomically claim one (domain occurrence, recipient, channel) slot
        via INSERT ... ON CONFLICT DO NOTHING against the unique
        `idempotency_key` index — returns the new row if this call won the
        race, or None if another concurrent writer already holds this key.
        This is the only correct way to prevent two concurrent callers from
        both proceeding to send: a SELECT-then-INSERT check is a race
        regardless of how carefully it's written, since either caller can
        pass the SELECT before either has committed its INSERT."""
        table = NotificationDelivery.__table__
        stmt = (
            pg_insert(table)
            .values(
                id=uuid.uuid4(),
                event_id=event_id,
                channel=channel,
                status=status,
                provider="",
                idempotency_key=idempotency_key,
                recipient_user_id=recipient_user_id,
                agency_id=agency_id,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(table.c.id)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        await self.session.flush()
        return await self.session.get(NotificationDelivery, row[0])

    async def update_result(
        self,
        delivery: NotificationDelivery,
        *,
        status: str,
        provider: str,
        provider_message_id: str | None = None,
        error_message: str | None = None,
        template_key: str | None = None,
        sent_at: datetime | None = None,
        recipient_phone_masked: str | None = None,
    ) -> NotificationDelivery:
        """Finalize a previously `reserve()`-d delivery row in place."""
        delivery.status = status
        delivery.provider = provider
        delivery.provider_message_id = provider_message_id
        delivery.error_message = error_message
        delivery.template_key = template_key
        delivery.sent_at = sent_at
        if recipient_phone_masked is not None:
            delivery.recipient_phone_masked = recipient_phone_masked
        self.session.add(delivery)
        await self.session.flush()
        return delivery

    # ── Part 6B-3: retry lifecycle ──────────────────────────────────────────
    #
    # All policy decisions (is this failure retryable? how long to back off?
    # has the attempt budget run out?) live in the service layer
    # (whatsapp_retry_policy.py / notification_dispatcher.py /
    # whatsapp_retry_worker.py) — every method below is a pure field-setter
    # so retry policy can change without touching persistence code.
    #
    # Lifecycle: a retryable send failure leaves the row in FAILED status
    # with `next_retry_at` set and `retry_exhausted_at` NULL — that pair is
    # what "in the retry queue" means (see claim_batch_for_retry). A
    # permanent failure, or a retryable one whose attempt budget is spent,
    # sets `retry_exhausted_at` and clears `next_retry_at` — same FAILED
    # status either way, since the spec's fixed status vocabulary has no
    # separate "retrying" state. CANCELLED/EXPIRED are reached only via
    # cancel_retry/expire_retry, never via the generic FAILED path.

    async def record_send_attempt(
        self,
        delivery: NotificationDelivery,
        *,
        status: str,
        provider: str,
        provider_message_id: str | None = None,
        error_message: str | None = None,
        failure_category: str | None = None,
        template_key: str | None = None,
        recipient_phone_masked: str | None = None,
        template_revision: int | None = None,
        template_content_sid: str | None = None,
        sent_at: datetime | None = None,
        next_retry_at: datetime | None = None,
        now: datetime,
    ) -> NotificationDelivery:
        """Record the outcome of one actual provider send attempt (never a
        pre-provider skip/gate result — those still go through
        `update_result`). Always increments `attempt_count` and stamps
        `last_attempt_at`; sets `next_retry_at` to whatever the caller
        decided (None means "not going into the retry queue")."""
        delivery.status = status
        delivery.provider = provider
        delivery.provider_message_id = provider_message_id
        delivery.error_message = error_message
        delivery.failure_category = failure_category
        if template_key is not None:
            delivery.template_key = template_key
        if recipient_phone_masked is not None:
            delivery.recipient_phone_masked = recipient_phone_masked
        if template_revision is not None:
            delivery.template_revision = template_revision
        if template_content_sid is not None:
            delivery.template_content_sid = template_content_sid
        delivery.sent_at = sent_at
        delivery.attempt_count += 1
        delivery.last_attempt_at = now
        delivery.next_retry_at = next_retry_at
        self.session.add(delivery)
        await self.session.flush()
        return delivery

    async def claim_batch_for_retry(
        self, *, limit: int, now: datetime, lease_seconds: int = 120
    ) -> list[NotificationDelivery]:
        """Atomically claim up to `limit` WhatsApp deliveries eligible for a
        retry attempt right now. Uses SELECT ... FOR UPDATE SKIP LOCKED so
        concurrent workers each get a disjoint set of rows rather than
        blocking on each other, then immediately pushes `next_retry_at` out
        by `lease_seconds` as a lease — if this worker crashes mid-attempt,
        the row becomes claimable again once the lease expires instead of
        being stuck forever."""
        table = NotificationDelivery.__table__
        lease_until = now + timedelta(seconds=lease_seconds)

        locked = await self.session.execute(
            select(table.c.id)
            .where(
                table.c.channel == NotificationChannel.WHATSAPP.value,
                table.c.status == "failed",
                table.c.next_retry_at.is_not(None),
                table.c.next_retry_at <= now,
                table.c.retry_exhausted_at.is_(None),
                table.c.deleted_at.is_(None),
            )
            .order_by(table.c.next_retry_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        ids = [row[0] for row in locked.all()]
        if not ids:
            return []

        await self.session.execute(
            update(table).where(table.c.id.in_(ids)).values(next_retry_at=lease_until)
        )
        await self.session.flush()

        result = await self.session.execute(
            select(NotificationDelivery).where(NotificationDelivery.id.in_(ids))
        )
        return list(result.scalars().all())

    async def schedule_next_retry(
        self,
        delivery: NotificationDelivery,
        *,
        next_retry_at: datetime,
        error_message: str | None,
        failure_category: str | None,
        now: datetime,
    ) -> NotificationDelivery:
        delivery.status = "failed"
        delivery.error_message = error_message
        delivery.failure_category = failure_category
        delivery.attempt_count += 1
        delivery.last_attempt_at = now
        delivery.next_retry_at = next_retry_at
        self.session.add(delivery)
        await self.session.flush()
        return delivery

    async def exhaust_retry(
        self,
        delivery: NotificationDelivery,
        *,
        error_message: str | None,
        failure_category: str | None,
        now: datetime,
    ) -> NotificationDelivery:
        delivery.status = "failed"
        delivery.error_message = error_message
        delivery.failure_category = failure_category
        delivery.attempt_count += 1
        delivery.last_attempt_at = now
        delivery.next_retry_at = None
        delivery.retry_exhausted_at = now
        self.session.add(delivery)
        await self.session.flush()
        return delivery

    async def record_retry_success(
        self,
        delivery: NotificationDelivery,
        *,
        provider: str,
        provider_message_id: str | None,
        now: datetime,
    ) -> NotificationDelivery:
        delivery.status = "sent"
        delivery.provider = provider
        delivery.provider_message_id = provider_message_id
        delivery.error_message = None
        delivery.attempt_count += 1
        delivery.last_attempt_at = now
        delivery.sent_at = now
        delivery.next_retry_at = None
        self.session.add(delivery)
        await self.session.flush()
        return delivery

    async def finalize_retry_as(
        self, delivery: NotificationDelivery, *, status: str, reason: str, now: datetime
    ) -> NotificationDelivery:
        """Terminate a claimed retry without a provider call — used by the
        retry worker when pre-attempt revalidation finds the retry is no
        longer valid/meaningful (opted out, template gone, business context
        resolved, etc.). `status` is any terminal status from
        whatsapp_retry_revalidation.RevalidationOutcome."""
        delivery.status = status
        delivery.error_message = reason
        delivery.next_retry_at = None
        if status == "cancelled":
            delivery.cancelled_at = now
        elif status == "expired":
            delivery.expired_at = now
        self.session.add(delivery)
        await self.session.flush()
        return delivery

    async def cancel_pending_retries_for_user(
        self, user_id: uuid.UUID, *, reason: str, now: datetime
    ) -> int:
        """Bulk-cancel every WhatsApp delivery still sitting in this user's
        retry queue (e.g. on STOP/opt-out) — never touches deliveries that
        already reached a terminal outcome."""
        table = NotificationDelivery.__table__
        stmt = (
            update(table)
            .where(
                table.c.recipient_user_id == user_id,
                table.c.channel == NotificationChannel.WHATSAPP.value,
                table.c.status == "failed",
                table.c.next_retry_at.is_not(None),
                table.c.retry_exhausted_at.is_(None),
                table.c.deleted_at.is_(None),
            )
            .values(
                status="cancelled",
                error_message=reason,
                next_retry_at=None,
                cancelled_at=now,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0

    async def list_for_agency(
        self,
        agency_id: uuid.UUID,
        *,
        channel: str = NotificationChannel.WHATSAPP.value,
        event_type: str | None = None,
        status_filter: str | None = None,
        template_key: str | None = None,
        user_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[NotificationDelivery], int]:
        """Tenant-isolated, filtered, paginated delivery history. Returns
        (page, total_count)."""
        base = (
            select(NotificationDelivery)
            .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
            .where(
                NotificationEvent.agency_id == agency_id,
                NotificationDelivery.channel == channel,
            )
        )
        if event_type:
            base = base.where(NotificationEvent.event_type == event_type)
        if status_filter:
            base = base.where(NotificationDelivery.status == status_filter)
        if template_key:
            base = base.where(NotificationDelivery.template_key == template_key)
        if user_id:
            base = base.where(NotificationDelivery.recipient_user_id == user_id)
        if date_from:
            base = base.where(NotificationDelivery.created_at >= date_from)
        if date_to:
            base = base.where(NotificationDelivery.created_at <= date_to)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = await self.session.scalar(count_stmt) or 0

        page_stmt = (
            base.order_by(NotificationDelivery.created_at.desc()).limit(limit).offset(offset)
        )
        result = await self.session.execute(page_stmt)
        return list(result.scalars().all()), total

    async def summary_counts_for_agency(
        self,
        agency_id: uuid.UUID,
        *,
        since: datetime,
        channel: str = NotificationChannel.WHATSAPP.value,
    ) -> dict[str, int]:
        """Status → count map for this agency's WhatsApp deliveries created
        since the given timestamp (used for 24h/7d summary windows)."""
        stmt = (
            select(NotificationDelivery.status, func.count())
            .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
            .where(
                NotificationEvent.agency_id == agency_id,
                NotificationDelivery.channel == channel,
                NotificationDelivery.created_at >= since,
            )
            .group_by(NotificationDelivery.status)
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def retry_metrics_for_agency(
        self, agency_id: uuid.UUID, *, channel: str = NotificationChannel.WHATSAPP.value
    ) -> dict[str, int]:
        """Current (not time-windowed) counts of the two retry-lifecycle
        states the admin metrics view needs: still in the retry queue, and
        permanently exhausted. Uses the denormalized `agency_id` column so
        this never needs a JOIN against notification_events."""
        table = NotificationDelivery.__table__
        queue_stmt = (
            select(func.count())
            .select_from(table)
            .where(
                table.c.agency_id == agency_id,
                table.c.channel == channel,
                table.c.status == "failed",
                table.c.next_retry_at.is_not(None),
                table.c.retry_exhausted_at.is_(None),
            )
        )
        exhausted_stmt = (
            select(func.count())
            .select_from(table)
            .where(
                table.c.agency_id == agency_id,
                table.c.channel == channel,
                table.c.retry_exhausted_at.is_not(None),
            )
        )
        retry_queue = await self.session.scalar(queue_stmt) or 0
        retry_exhausted = await self.session.scalar(exhausted_stmt) or 0
        return {"retry_queue": retry_queue, "retry_exhausted": retry_exhausted}

    async def top_failure_category_for_agency(
        self,
        agency_id: uuid.UUID,
        *,
        since: datetime,
        channel: str = NotificationChannel.WHATSAPP.value,
    ) -> str | None:
        """Most frequent safe `failure_category` in the window — never the
        raw `error_message`, which may contain provider-specific detail."""
        stmt = (
            select(NotificationDelivery.failure_category, func.count())
            .where(
                NotificationDelivery.agency_id == agency_id,
                NotificationDelivery.channel == channel,
                NotificationDelivery.failure_category.is_not(None),
                NotificationDelivery.created_at >= since,
            )
            .group_by(NotificationDelivery.failure_category)
            .order_by(func.count().desc())
            .limit(1)
        )
        row = (await self.session.execute(stmt)).first()
        return row[0] if row else None

    async def latest_error_for_agency(
        self,
        agency_id: uuid.UUID,
        *,
        channel: str = NotificationChannel.WHATSAPP.value,
    ) -> NotificationDelivery | None:
        stmt = (
            select(NotificationDelivery)
            .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
            .where(
                NotificationEvent.agency_id == agency_id,
                NotificationDelivery.channel == channel,
                NotificationDelivery.error_message.is_not(None),
            )
            .order_by(NotificationDelivery.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def latest_for_user(
        self,
        user_id: uuid.UUID,
        *,
        channel: str = NotificationChannel.WHATSAPP.value,
        status_filter: str | None = None,
    ) -> NotificationDelivery | None:
        stmt = (
            select(NotificationDelivery)
            .where(
                NotificationDelivery.recipient_user_id == user_id,
                NotificationDelivery.channel == channel,
            )
            .order_by(NotificationDelivery.created_at.desc())
            .limit(1)
        )
        if status_filter:
            stmt = stmt.where(NotificationDelivery.status == status_filter)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class NotificationEventPreferenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: uuid.UUID) -> dict[str, NotificationEventPreference]:
        stmt = select(NotificationEventPreference).where(
            NotificationEventPreference.user_id == user_id,
            NotificationEventPreference.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return {row.event_type: row for row in result.scalars().all()}

    async def upsert_whatsapp_toggle(
        self,
        user_id: uuid.UUID,
        event_type: str,
        whatsapp_enabled: bool,
        updated_by_user_id: uuid.UUID,
    ) -> NotificationEventPreference:
        """INSERT ... ON CONFLICT DO UPDATE against the unique (user_id,
        event_type) constraint — never produces a duplicate row even under
        concurrent writes for the same event."""
        table = NotificationEventPreference.__table__
        stmt = (
            pg_insert(table)
            .values(
                id=uuid.uuid4(),
                user_id=user_id,
                event_type=event_type,
                whatsapp_enabled=whatsapp_enabled,
                updated_by_user_id=updated_by_user_id,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "event_type"],
                set_={
                    "whatsapp_enabled": whatsapp_enabled,
                    "updated_by_user_id": updated_by_user_id,
                    "updated_at": datetime.now(UTC),
                },
            )
            .returning(table.c.id)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        await self.session.flush()
        assert row is not None
        pref = await self.session.get(NotificationEventPreference, row[0])
        assert pref is not None
        return pref
