"""Backend tests for the Part 6B-3 WhatsApp admin metrics additions:
retry queue / retry exhausted counts, success rate, read rate, and top
failure category — all tenant-isolated and safe under zero data.
"""

# ruff: noqa: F811 -- `ctx` is an imported fixture reused as a test-method
# parameter name (standard pytest cross-module fixture reuse).
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.db.session import AsyncSessionLocal
from app.models.enums import NotificationChannel, NotificationDeliveryStatus
from app.models.notification import NotificationDelivery, NotificationEvent
from app.services.whatsapp_admin_service import build_agency_summary
from app.tests.test_whatsapp_event_dispatch import Ctx, ctx  # noqa: F401


async def _seed_delivery(
    ctx: Ctx,
    *,
    status: str,
    failure_category: str | None = None,
    next_retry_at: datetime | None = None,
    retry_exhausted_at: datetime | None = None,
) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        event = NotificationEvent(
            id=uuid.uuid4(), event_type="brief.created", payload={}, agency_id=ctx.agency_id
        )
        session.add(event)
        await session.flush()
        delivery = NotificationDelivery(
            id=uuid.uuid4(),
            event_id=event.id,
            channel=NotificationChannel.WHATSAPP.value,
            status=status,
            provider="twilio_production",
            agency_id=ctx.agency_id,
            failure_category=failure_category,
            next_retry_at=next_retry_at,
            retry_exhausted_at=retry_exhausted_at,
            idempotency_key=f"test-metrics-{uuid.uuid4().hex}",
        )
        session.add(delivery)
        await session.commit()
        return delivery.id


async def _delete(delivery_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        d = await session.get(NotificationDelivery, delivery_id)
        if d is not None:
            await session.delete(d)
        await session.commit()


class TestWhatsAppAdminMetrics:
    async def test_zero_data_is_division_by_zero_safe(self, ctx: Ctx) -> None:
        async with AsyncSessionLocal() as session:
            summary = await build_agency_summary(session, agency_id=ctx.agency_id, is_demo=False)
        assert summary.retry_queue == 0
        assert summary.retry_exhausted == 0
        assert summary.delivery_success_rate_7d is None
        assert summary.read_rate_7d is None
        assert summary.top_failure_category_7d is None

    async def test_retry_queue_and_exhausted_counts(self, ctx: Ctx) -> None:
        now = datetime.now(UTC)
        queued_id = await _seed_delivery(
            ctx,
            status=NotificationDeliveryStatus.FAILED.value,
            next_retry_at=now + timedelta(minutes=5),
        )
        exhausted_id = await _seed_delivery(
            ctx, status=NotificationDeliveryStatus.FAILED.value, retry_exhausted_at=now
        )
        try:
            async with AsyncSessionLocal() as session:
                summary = await build_agency_summary(
                    session, agency_id=ctx.agency_id, is_demo=False
                )
            assert summary.retry_queue == 1
            assert summary.retry_exhausted == 1
        finally:
            await _delete(queued_id)
            await _delete(exhausted_id)

    async def test_success_and_read_rate_computed_correctly(self, ctx: Ctx) -> None:
        ids = [
            await _seed_delivery(ctx, status=NotificationDeliveryStatus.SENT.value),
            await _seed_delivery(ctx, status=NotificationDeliveryStatus.DELIVERED.value),
            await _seed_delivery(ctx, status=NotificationDeliveryStatus.READ.value),
            await _seed_delivery(ctx, status=NotificationDeliveryStatus.FAILED.value),
        ]
        try:
            async with AsyncSessionLocal() as session:
                summary = await build_agency_summary(
                    session, agency_id=ctx.agency_id, is_demo=False
                )
            # 3 successful (sent/delivered/read) out of 4 attempted (incl. failed)
            assert summary.delivery_success_rate_7d == 0.75
            # 1 read out of (1 delivered + 1 read)
            assert summary.read_rate_7d == 0.5
        finally:
            for i in ids:
                await _delete(i)

    async def test_top_failure_category_and_tenant_isolation(self, ctx: Ctx) -> None:
        ids = [
            await _seed_delivery(
                ctx, status=NotificationDeliveryStatus.FAILED.value, failure_category="timeout"
            ),
            await _seed_delivery(
                ctx, status=NotificationDeliveryStatus.FAILED.value, failure_category="timeout"
            ),
            await _seed_delivery(
                ctx,
                status=NotificationDeliveryStatus.FAILED.value,
                failure_category="invalid_recipient",
            ),
        ]
        try:
            async with AsyncSessionLocal() as session:
                summary = await build_agency_summary(
                    session, agency_id=ctx.agency_id, is_demo=False
                )
            assert summary.top_failure_category_7d == "timeout"

            # A different, never-seeded agency must see none of this.
            async with AsyncSessionLocal() as session:
                other_summary = await build_agency_summary(
                    session, agency_id=uuid.uuid4(), is_demo=False
                )
            assert other_summary.top_failure_category_7d is None
            assert other_summary.retry_queue == 0
        finally:
            for i in ids:
                await _delete(i)
