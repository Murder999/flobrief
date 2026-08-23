"""Backend tests for WhatsApp retry lifecycle (Part 6B-3).

Covers: retryable/non-retryable classification, exponential backoff+jitter,
atomic concurrent claim, revalidation before a retry fires (opt-out,
template gone, business context resolved), and full retry-batch integration
via the fake in-process provider (never a real Twilio call).
"""

# ruff: noqa: F811 -- `ctx`/`approve_template` are imported fixtures reused
# as test-method parameter names, the standard pytest cross-module fixture
# pattern; ruff's static analysis can't see the pytest fixture-injection
# machinery that makes this correct (same pattern as F401 below).
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from app.db.session import AsyncSessionLocal
from app.models.client_invoice import ClientInvoice
from app.models.enums import (
    BriefStatus,
    ClientInvoiceDocumentType,
    ClientInvoiceStatus,
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationEventType,
    WhatsAppTemplateStatus,
)
from app.models.notification import NotificationDelivery, NotificationEvent
from app.models.user import User
from app.repositories.notification import NotificationDeliveryRepository
from app.repositories.whatsapp_template import WhatsAppTemplateRepository
from app.services.whatsapp_provider import WhatsAppDeliveryResult
from app.services.whatsapp_retry_policy import (
    MAX_ATTEMPTS,
    compute_backoff_seconds,
    is_retryable,
)
from app.services.whatsapp_retry_worker import run_retry_batch
from app.tests.test_whatsapp_event_dispatch import Ctx, approve_template, ctx  # noqa: F401

# ── Fake providers ───────────────────────────────────────────────────────────


@dataclass
class _FakeRetryProvider:
    """Fails N times with a given category, then succeeds. Records calls so
    tests can assert whether the provider was ever actually invoked."""

    fail_times: int = 1
    fail_category: str = "timeout"
    calls: list[str] = field(default_factory=list)

    def get_provider_name(self) -> str:
        return "twilio_production"

    def send_template_message(self, to_phone, content_sid, variables) -> WhatsAppDeliveryResult:
        self.calls.append(to_phone)
        if len(self.calls) <= self.fail_times:
            return WhatsAppDeliveryResult(
                status=NotificationDeliveryStatus.FAILED.value,
                provider="twilio_production",
                provider_message_id=None,
                error_message="simulated transient failure",
                failure_category=self.fail_category,
            )
        return WhatsAppDeliveryResult(
            status=NotificationDeliveryStatus.SENT.value,
            provider="twilio_production",
            provider_message_id="SMretry" + uuid.uuid4().hex[:8],
            error_message=None,
        )


def _patched_retry_provider(provider: object):
    from unittest.mock import patch

    return patch(
        "app.services.whatsapp_retry_worker.WhatsAppProviderFactory.get_provider",
        return_value=provider,
    )


# ── Seed helper: a WhatsApp delivery already sitting in the retry queue ─────


async def _seed_failed_retry_delivery(
    ctx: Ctx,
    *,
    template_code: str,
    template_revision: int,
    attempt_count: int = 1,
    next_retry_at: datetime | None = None,
    event_type: str = NotificationEventType.BRIEF_CREATED.value,
    payload: dict | None = None,
    recipient_id: uuid.UUID | None = None,
) -> uuid.UUID:
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        event = NotificationEvent(
            id=uuid.uuid4(),
            event_type=event_type,
            payload=payload or {},
            agency_id=ctx.agency_id,
            brand_id=ctx.brand_id,
        )
        session.add(event)
        await session.flush()

        delivery = NotificationDelivery(
            id=uuid.uuid4(),
            event_id=event.id,
            channel=NotificationChannel.WHATSAPP.value,
            status=NotificationDeliveryStatus.FAILED.value,
            provider="twilio_production",
            recipient_user_id=recipient_id or ctx.owner_id,
            agency_id=ctx.agency_id,
            template_key=template_code,
            template_revision=template_revision,
            attempt_count=attempt_count,
            next_retry_at=next_retry_at or (now - timedelta(seconds=5)),
            idempotency_key=f"test-retry-{uuid.uuid4().hex}",
        )
        session.add(delivery)
        await session.commit()
        return delivery.id


async def _get_delivery(delivery_id: uuid.UUID) -> NotificationDelivery:
    async with AsyncSessionLocal() as session:
        return await session.get(NotificationDelivery, delivery_id)


async def _delete_delivery(delivery_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        d = await session.get(NotificationDelivery, delivery_id)
        if d is not None:
            await session.delete(d)
        await session.commit()


# ── Pure policy tests ────────────────────────────────────────────────────────


class TestRetryPolicy:
    def test_retryable_categories(self) -> None:
        for c in ("timeout", "connection_error", "network_error", "server_error", "rate_limited"):
            assert is_retryable(c) is True

    def test_non_retryable_categories(self) -> None:
        for c in ("invalid_recipient", "no_consent", "opt_out", "template_missing", "auth", None):
            assert is_retryable(c) is False

    def test_backoff_grows_and_caps(self) -> None:
        d1 = compute_backoff_seconds(1)
        d3 = compute_backoff_seconds(3)
        d_high = compute_backoff_seconds(50)
        assert d1 < d3
        assert d_high <= 3600 * 1.2 + 1  # capped + jitter headroom

    def test_backoff_jitter_stays_within_bounds(self) -> None:
        import random

        rng = random.Random(42)
        for attempt in range(1, MAX_ATTEMPTS + 1):
            delay = compute_backoff_seconds(attempt, rng=rng)
            base = min(30.0 * (2 ** (attempt - 1)), 3600.0)
            assert base * 0.8 - 1 <= delay <= base * 1.2 + 1


# ── Concurrency ──────────────────────────────────────────────────────────────


class TestConcurrentClaim:
    async def test_two_concurrent_claims_never_double_claim_the_same_row(self, ctx) -> None:
        delivery_id = await _seed_failed_retry_delivery(
            ctx, template_code="brief_created", template_revision=1
        )
        try:

            async def _claim() -> list[uuid.UUID]:
                async with AsyncSessionLocal() as db:
                    repo = NotificationDeliveryRepository(db)
                    claimed = await repo.claim_batch_for_retry(limit=10, now=datetime.now(UTC))
                    await db.commit()
                    return [d.id for d in claimed]

            results = await asyncio.gather(_claim(), _claim())
            combined = results[0] + results[1]
            assert combined.count(delivery_id) == 1
        finally:
            await _delete_delivery(delivery_id)

    async def test_claim_does_not_pick_up_non_eligible_rows(self, ctx) -> None:
        """A future next_retry_at must never be claimed."""
        future_id = await _seed_failed_retry_delivery(
            ctx,
            template_code="brief_created",
            template_revision=1,
            next_retry_at=datetime.now(UTC) + timedelta(hours=1),
        )
        try:
            async with AsyncSessionLocal() as db:
                repo = NotificationDeliveryRepository(db)
                claimed = await repo.claim_batch_for_retry(limit=10, now=datetime.now(UTC))
                await db.commit()
            assert future_id not in [d.id for d in claimed]
        finally:
            await _delete_delivery(future_id)


# ── End-to-end retry batch ───────────────────────────────────────────────────


class TestRetryBatchIntegration:
    async def test_retryable_failure_then_success_transitions_to_sent(
        self, ctx, approve_template
    ) -> None:
        await approve_template(
            "brief_created", content_sid="HXtest123", variable_schema={"1": "recipient_first_name"}
        )
        delivery_id = await _seed_failed_retry_delivery(
            ctx, template_code="brief_created", template_revision=1, attempt_count=1
        )
        provider = _FakeRetryProvider(fail_times=0)  # succeeds on the retry attempt
        try:
            with _patched_retry_provider(provider):
                processed = await run_retry_batch()
            assert processed >= 1
            delivery = await _get_delivery(delivery_id)
            assert delivery.status == NotificationDeliveryStatus.SENT.value
            assert delivery.provider_message_id is not None
            assert delivery.next_retry_at is None
            assert delivery.attempt_count == 2
        finally:
            await _delete_delivery(delivery_id)

    async def test_retryable_failure_reschedules_with_backoff(self, ctx, approve_template) -> None:
        await approve_template(
            "brief_created", content_sid="HXtest123", variable_schema={"1": "recipient_first_name"}
        )
        delivery_id = await _seed_failed_retry_delivery(
            ctx, template_code="brief_created", template_revision=1, attempt_count=1
        )
        provider = _FakeRetryProvider(fail_times=99, fail_category="timeout")
        try:
            with _patched_retry_provider(provider):
                await run_retry_batch()
            delivery = await _get_delivery(delivery_id)
            assert delivery.status == NotificationDeliveryStatus.FAILED.value
            assert delivery.next_retry_at is not None
            assert delivery.next_retry_at > datetime.now(UTC)
            assert delivery.retry_exhausted_at is None
            assert delivery.attempt_count == 2
        finally:
            await _delete_delivery(delivery_id)

    async def test_max_attempts_exhausted_stops_retrying(self, ctx, approve_template) -> None:
        await approve_template(
            "brief_created", content_sid="HXtest123", variable_schema={"1": "recipient_first_name"}
        )
        delivery_id = await _seed_failed_retry_delivery(
            ctx,
            template_code="brief_created",
            template_revision=1,
            attempt_count=MAX_ATTEMPTS,  # already at budget
        )
        provider = _FakeRetryProvider(fail_times=99, fail_category="timeout")
        try:
            with _patched_retry_provider(provider):
                await run_retry_batch()
            delivery = await _get_delivery(delivery_id)
            assert delivery.status == NotificationDeliveryStatus.FAILED.value
            assert delivery.next_retry_at is None
            assert delivery.retry_exhausted_at is not None
        finally:
            await _delete_delivery(delivery_id)

    async def test_permanent_failure_category_is_never_retried_by_worker(
        self, ctx, approve_template
    ) -> None:
        await approve_template(
            "brief_created", content_sid="HXtest123", variable_schema={"1": "recipient_first_name"}
        )
        delivery_id = await _seed_failed_retry_delivery(
            ctx, template_code="brief_created", template_revision=1, attempt_count=1
        )
        provider = _FakeRetryProvider(fail_times=99, fail_category="invalid_recipient")
        try:
            with _patched_retry_provider(provider):
                await run_retry_batch()
            delivery = await _get_delivery(delivery_id)
            assert delivery.status == NotificationDeliveryStatus.FAILED.value
            assert delivery.next_retry_at is None
            assert delivery.retry_exhausted_at is not None
        finally:
            await _delete_delivery(delivery_id)


# ── Revalidation ──────────────────────────────────────────────────────────────


class TestRetryRevalidation:
    async def test_opt_out_before_retry_cancels_without_calling_provider(
        self, ctx, approve_template
    ) -> None:
        await approve_template(
            "brief_created", content_sid="HXtest123", variable_schema={"1": "recipient_first_name"}
        )
        delivery_id = await _seed_failed_retry_delivery(
            ctx, template_code="brief_created", template_revision=1, attempt_count=1
        )
        async with AsyncSessionLocal() as session:
            user = await session.get(User, ctx.owner_id)
            user.whatsapp_opt_in = False
            session.add(user)
            await session.commit()

        provider = _FakeRetryProvider(fail_times=0)
        try:
            with _patched_retry_provider(provider):
                await run_retry_batch()
            delivery = await _get_delivery(delivery_id)
            assert delivery.status == NotificationDeliveryStatus.SKIPPED_NO_CONSENT.value
            assert provider.calls == []  # never actually called Twilio
        finally:
            await _delete_delivery(delivery_id)

    async def test_template_disabled_before_retry_skips_without_provider_call(
        self, ctx, approve_template
    ) -> None:
        await approve_template(
            "brief_created", content_sid="HXtest123", variable_schema={"1": "recipient_first_name"}
        )
        delivery_id = await _seed_failed_retry_delivery(
            ctx, template_code="brief_created", template_revision=1, attempt_count=1
        )
        async with AsyncSessionLocal() as session:
            repo = WhatsAppTemplateRepository(session)
            tpl = await repo.get_by_code("brief_created")
            tpl.status = WhatsAppTemplateStatus.DISABLED.value
            session.add(tpl)
            await session.commit()

        provider = _FakeRetryProvider(fail_times=0)
        try:
            with _patched_retry_provider(provider):
                await run_retry_batch()
            delivery = await _get_delivery(delivery_id)
            assert delivery.status == NotificationDeliveryStatus.SKIPPED_TEMPLATE_MISSING.value
            assert provider.calls == []
        finally:
            await _delete_delivery(delivery_id)
            async with AsyncSessionLocal() as session:
                repo = WhatsAppTemplateRepository(session)
                tpl = await repo.get_by_code("brief_created")
                tpl.status = WhatsAppTemplateStatus.DRAFT.value
                session.add(tpl)
                await session.commit()

    async def test_stale_template_revision_skips_retry(self, ctx, approve_template) -> None:
        await approve_template(
            "brief_created", content_sid="HXtest123", variable_schema={"1": "recipient_first_name"}
        )
        # Delivery snapshotted revision 1, but the live template has since
        # moved on (simulated by forcing the live revision ahead directly).
        async with AsyncSessionLocal() as session:
            repo = WhatsAppTemplateRepository(session)
            tpl = await repo.get_by_code("brief_created")
            tpl.revision = 5
            session.add(tpl)
            await session.commit()

        delivery_id = await _seed_failed_retry_delivery(
            ctx, template_code="brief_created", template_revision=1, attempt_count=1
        )
        provider = _FakeRetryProvider(fail_times=0)
        try:
            with _patched_retry_provider(provider):
                await run_retry_batch()
            delivery = await _get_delivery(delivery_id)
            assert delivery.status == NotificationDeliveryStatus.SKIPPED_TEMPLATE_MISSING.value
            assert provider.calls == []
        finally:
            await _delete_delivery(delivery_id)
            async with AsyncSessionLocal() as session:
                repo = WhatsAppTemplateRepository(session)
                tpl = await repo.get_by_code("brief_created")
                tpl.revision = 1
                session.add(tpl)
                await session.commit()

    async def test_brief_completed_expires_pending_reminder_retry(
        self, ctx, approve_template
    ) -> None:
        await approve_template(
            "brief_due_soon", content_sid="HXdue123", variable_schema={"1": "due_date"}
        )
        async with AsyncSessionLocal() as session:
            from app.models.brief import Brief

            brief = await session.get(Brief, ctx.brief_id)
            brief.status = BriefStatus.COMPLETED.value
            session.add(brief)
            await session.commit()

        delivery_id = await _seed_failed_retry_delivery(
            ctx,
            template_code="brief_due_soon",
            template_revision=1,
            attempt_count=1,
            event_type=NotificationEventType.CALENDAR_ITEM_DUE.value,
            payload={"brief_id": str(ctx.brief_id)},
        )
        provider = _FakeRetryProvider(fail_times=0)
        try:
            with _patched_retry_provider(provider):
                await run_retry_batch()
            delivery = await _get_delivery(delivery_id)
            assert delivery.status == NotificationDeliveryStatus.EXPIRED.value
            assert provider.calls == []
        finally:
            await _delete_delivery(delivery_id)

    async def test_invoice_paid_expires_pending_reminder_retry(self, ctx, approve_template) -> None:
        await approve_template(
            "invoice_overdue", content_sid="HXinv123", variable_schema={"1": "invoice_number"}
        )
        today = date(2026, 7, 29)
        async with AsyncSessionLocal() as session:
            invoice = ClientInvoice(
                id=uuid.uuid4(),
                agency_id=ctx.agency_id,
                brand_id=ctx.brand_id,
                invoice_number=f"INV-TEST-{uuid.uuid4().hex[:8]}",
                document_type=ClientInvoiceDocumentType.DRAFT_INVOICE.value,
                issue_date=today - timedelta(days=10),
                due_date=today - timedelta(days=1),
                status=ClientInvoiceStatus.PAID.value,
                total_cents=10000,
                subtotal_cents=10000,
            )
            session.add(invoice)
            await session.commit()
            invoice_id = invoice.id

        delivery_id = await _seed_failed_retry_delivery(
            ctx,
            template_code="invoice_overdue",
            template_revision=1,
            attempt_count=1,
            event_type=NotificationEventType.INVOICE_OVERDUE.value,
            payload={"invoice_id": str(invoice_id)},
        )
        provider = _FakeRetryProvider(fail_times=0)
        try:
            with _patched_retry_provider(provider):
                await run_retry_batch()
            delivery = await _get_delivery(delivery_id)
            assert delivery.status == NotificationDeliveryStatus.EXPIRED.value
            assert provider.calls == []
        finally:
            await _delete_delivery(delivery_id)
            async with AsyncSessionLocal() as session:
                inv = await session.get(ClientInvoice, invoice_id)
                if inv is not None:
                    await session.delete(inv)
                await session.commit()
