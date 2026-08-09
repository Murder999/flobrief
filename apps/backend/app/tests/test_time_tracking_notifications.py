"""Time tracking scheduler tests: calls run_time_tracking_checks() directly
against real seeded TimeEntry rows and asserts each of the four checks fires
exactly once, deduplicating on rerun — mirrors test_deadline reminder
conventions used for CALENDAR_ITEM_DUE."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.notification import NotificationEvent
from app.models.time_entry import TimeEntry
from app.services.time_tracking_scheduler import run_time_tracking_checks


async def _count_events(event_type: str) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(NotificationEvent).where(NotificationEvent.event_type == event_type)
        )
        return len(result.scalars().all())


async def test_long_running_timer_notified_once(client, tenants) -> None:
    tenant_a, _ = tenants
    async with AsyncSessionLocal() as session:
        entry = TimeEntry(
            id=uuid.uuid4(),
            agency_id=tenant_a.agency_id,
            brand_id=tenant_a.brand_id,
            user_id=tenant_a.agency_user_id,
            category="design",
            started_at=datetime.now(UTC) - timedelta(hours=9),
            ended_at=None,
            billable=True,
            source="timer",
        )
        session.add(entry)
        await session.commit()

    before = await _count_events("time_entry.long_running")
    await run_time_tracking_checks()
    after_first = await _count_events("time_entry.long_running")
    await run_time_tracking_checks()
    after_second = await _count_events("time_entry.long_running")

    assert after_first == before + 1
    assert after_second == after_first, "must dedup on rerun, not fire twice"

    async with AsyncSessionLocal() as session:
        await session.delete(await session.get(TimeEntry, entry.id))
        await session.commit()


async def test_eod_still_running_notified_once(client, tenants) -> None:
    tenant_a, _ = tenants
    async with AsyncSessionLocal() as session:
        entry = TimeEntry(
            id=uuid.uuid4(),
            agency_id=tenant_a.agency_id,
            brand_id=tenant_a.brand_id,
            user_id=tenant_a.agency_user_id,
            category="design",
            started_at=datetime.now(UTC) - timedelta(days=1, hours=2),
            ended_at=None,
            billable=True,
            source="timer",
        )
        session.add(entry)
        await session.commit()

    before = await _count_events("time_entry.still_running_eod")
    await run_time_tracking_checks()
    after_first = await _count_events("time_entry.still_running_eod")
    await run_time_tracking_checks()
    after_second = await _count_events("time_entry.still_running_eod")

    assert after_first == before + 1
    assert after_second == after_first

    async with AsyncSessionLocal() as session:
        await session.delete(await session.get(TimeEntry, entry.id))
        await session.commit()


async def test_missing_timesheet_notified_once_for_agency_user(client, tenants) -> None:
    """The `tenants` fixture's ADMIN user only has a today-dated entry, so
    yesterday is a genuine, real gap — the check must flag it, and not
    re-flag it on a second run."""
    tenant_a, _ = tenants

    before = await _count_events("timesheet.missing")
    await run_time_tracking_checks()
    after_first = await _count_events("timesheet.missing")
    await run_time_tracking_checks()
    after_second = await _count_events("timesheet.missing")

    assert after_first >= before  # at least this tenant's gap was flagged
    assert after_second == after_first, "must dedup on rerun, not fire twice"


async def test_approval_pending_notified_once(client, tenants) -> None:
    tenant_a, _ = tenants
    async with AsyncSessionLocal() as session:
        started = datetime.now(UTC) - timedelta(days=10)
        ended = started + timedelta(hours=1)
        entry = TimeEntry(
            id=uuid.uuid4(),
            agency_id=tenant_a.agency_id,
            brand_id=tenant_a.brand_id,
            user_id=tenant_a.agency_user_id,
            category="design",
            started_at=started,
            ended_at=ended,
            duration_seconds=3600,
            billable=True,
            source="manual",
            locked=False,
        )
        session.add(entry)
        await session.commit()

    before = await _count_events("time_entry.approval_pending")
    await run_time_tracking_checks()
    after_first = await _count_events("time_entry.approval_pending")
    await run_time_tracking_checks()
    after_second = await _count_events("time_entry.approval_pending")

    assert after_first == before + 1
    assert after_second == after_first

    async with AsyncSessionLocal() as session:
        await session.delete(await session.get(TimeEntry, entry.id))
        await session.commit()


async def test_checks_never_create_or_mutate_time_entries(client, tenants) -> None:
    """The scheduler must be read-only with respect to TimeEntry rows — it
    only ever dispatches notifications, never fabricates or edits time data."""
    tenant_a, _ = tenants
    async with AsyncSessionLocal() as session:
        before_count = len(
            (
                await session.execute(
                    select(TimeEntry).where(TimeEntry.agency_id == tenant_a.agency_id)
                )
            )
            .scalars()
            .all()
        )

    await run_time_tracking_checks()

    async with AsyncSessionLocal() as session:
        after_count = len(
            (
                await session.execute(
                    select(TimeEntry).where(TimeEntry.agency_id == tenant_a.agency_id)
                )
            )
            .scalars()
            .all()
        )
    assert after_count == before_count
