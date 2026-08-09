"""Time tracking background scheduler: long-running-timer nudges,
end-of-day-still-running reminders, missing-timesheet notices, and
approval-pending digests. Structurally mirrors deadline_scheduler.py.

No emission here ever creates or mutates a TimeEntry row — this module only
reads existing rows and dispatches notifications. Time capture itself only
ever happens via an explicit timer start or manual entry (see
time_tracking_service.py), never from this background loop."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission, get_permissions_for_agency_role
from app.core.time_utils import utc_today
from app.db.session import AsyncSessionLocal
from app.models.agency_member import AgencyMember
from app.models.enums import NotificationEventType
from app.models.notification import NotificationEvent
from app.models.time_entry import TimeEntry
from app.services.notification_dispatcher import NotificationDispatcher

log = logging.getLogger(__name__)

_LONG_RUNNING_HOURS = 8
_APPROVAL_PENDING_DAYS = 7
_DEDUP_HOURS = 23  # suppress repeat reminders within 23h, mirrors deadline_scheduler


async def _already_notified(
    db: AsyncSession, event_type: str, entity_key: str, entity_value: str
) -> bool:
    cutoff = datetime.now(UTC) - timedelta(hours=_DEDUP_HOURS)
    stmt = (
        select(NotificationEvent.id)
        .where(
            NotificationEvent.event_type == event_type,
            NotificationEvent.created_at >= cutoff,
            func.jsonb_extract_path_text(cast(NotificationEvent.payload, JSONB), entity_key)
            == entity_value,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def _check_long_running_timers(db: AsyncSession) -> None:
    """Nudges a user whose running timer has been active longer than
    _LONG_RUNNING_HOURS — not surveillance, just a courtesy reminder to the
    same person who started it, mirroring how CALENDAR_ITEM_DUE nudges
    the brief owner about their own deadline."""
    cutoff = datetime.now(UTC) - timedelta(hours=_LONG_RUNNING_HOURS)
    stmt = select(TimeEntry).where(
        TimeEntry.ended_at.is_(None),
        TimeEntry.deleted_at.is_(None),
        TimeEntry.started_at <= cutoff,
    )
    result = await db.execute(stmt)
    entries = result.scalars().all()

    dispatcher = NotificationDispatcher(db)
    for entry in entries:
        entry_id_str = str(entry.id)
        if await _already_notified(
            db, NotificationEventType.TIME_ENTRY_LONG_RUNNING.value, "entry_id", entry_id_str
        ):
            continue
        try:
            elapsed_hours = round((datetime.now(UTC) - entry.started_at).total_seconds() / 3600, 1)
            await dispatcher.emit(
                NotificationEventType.TIME_ENTRY_LONG_RUNNING.value,
                payload={
                    "entry_id": entry_id_str,
                    "elapsed_hours": elapsed_hours,
                    "summary": f"Zamanlayıcınız {elapsed_hours} saattir çalışıyor. Unuttunuz mu?",
                },
                agency_id=entry.agency_id,
                brand_id=entry.brand_id,
                actor_user_id=None,
                recipient_ids=[entry.user_id],
            )
            await db.commit()
        except Exception:
            await db.rollback()
            log.exception("Failed to send TIME_ENTRY_LONG_RUNNING for entry %s", entry_id_str)


async def _check_still_running_eod(db: AsyncSession) -> None:
    """A timer still running from a *previous* calendar UTC day — the
    person likely forgot to stop it before leaving. Distinct from the
    long-running check, which fires the same day regardless of date
    rollover."""
    today_start = datetime.combine(utc_today(), datetime.min.time()).replace(tzinfo=UTC)
    stmt = select(TimeEntry).where(
        TimeEntry.ended_at.is_(None),
        TimeEntry.deleted_at.is_(None),
        TimeEntry.started_at < today_start,
    )
    result = await db.execute(stmt)
    entries = result.scalars().all()

    dispatcher = NotificationDispatcher(db)
    for entry in entries:
        entry_id_str = str(entry.id)
        if await _already_notified(
            db, NotificationEventType.TIME_ENTRY_STILL_RUNNING_EOD.value, "entry_id", entry_id_str
        ):
            continue
        try:
            await dispatcher.emit(
                NotificationEventType.TIME_ENTRY_STILL_RUNNING_EOD.value,
                payload={
                    "entry_id": entry_id_str,
                    "started_at": entry.started_at.isoformat(),
                    "summary": (
                        "Dünden beri çalışan bir zamanlayıcınız var. " "Durdurmayı unuttunuz mu?"
                    ),
                },
                agency_id=entry.agency_id,
                brand_id=entry.brand_id,
                actor_user_id=None,
                recipient_ids=[entry.user_id],
            )
            await db.commit()
        except Exception:
            await db.rollback()
            log.exception("Failed to send TIME_ENTRY_STILL_RUNNING_EOD for entry %s", entry_id_str)


async def _check_missing_timesheets(db: AsyncSession) -> None:
    """Any active member with TIME_ENTRY_LOG who logged zero entries for
    yesterday (the most recently completed calendar day). No holiday/weekend
    calendar exists to exclude non-workdays — a deliberate Part-1
    simplification, documented in the plan."""
    yesterday = utc_today() - timedelta(days=1)
    day_start = datetime.combine(yesterday, datetime.min.time()).replace(tzinfo=UTC)
    day_end = datetime.combine(yesterday, datetime.max.time()).replace(tzinfo=UTC)

    agency_rows = await db.execute(
        select(AgencyMember.agency_id).where(AgencyMember.deleted_at.is_(None)).distinct()
    )
    agency_ids = [row[0] for row in agency_rows]

    dispatcher = NotificationDispatcher(db)
    for agency_id in agency_ids:
        member_rows = await db.execute(
            select(AgencyMember.user_id, AgencyMember.role).where(
                AgencyMember.agency_id == agency_id,
                AgencyMember.deleted_at.is_(None),
                AgencyMember.status == "active",
            )
        )
        loggers = [
            row.user_id
            for row in member_rows
            if Permission.TIME_ENTRY_LOG in get_permissions_for_agency_role(row.role)
        ]
        if not loggers:
            continue

        logged_stmt = (
            select(TimeEntry.user_id)
            .where(
                TimeEntry.agency_id == agency_id,
                TimeEntry.deleted_at.is_(None),
                TimeEntry.started_at >= day_start,
                TimeEntry.started_at <= day_end,
            )
            .distinct()
        )
        logged_result = await db.execute(logged_stmt)
        logged_user_ids = {row[0] for row in logged_result}

        for user_id in loggers:
            if user_id in logged_user_ids:
                continue
            dedup_key = f"{agency_id}:{user_id}:{yesterday.isoformat()}"
            if await _already_notified(
                db, NotificationEventType.TIMESHEET_MISSING.value, "dedup_key", dedup_key
            ):
                continue
            try:
                await dispatcher.emit(
                    NotificationEventType.TIMESHEET_MISSING.value,
                    payload={
                        "dedup_key": dedup_key,
                        "missing_date": yesterday.isoformat(),
                        "summary": f"{yesterday.isoformat()} için zaman kaydınız bulunmuyor.",
                    },
                    agency_id=agency_id,
                    brand_id=None,
                    actor_user_id=None,
                    recipient_ids=[user_id],
                )
                await db.commit()
            except Exception:
                await db.rollback()
                log.exception(
                    "Failed to send TIMESHEET_MISSING for user %s agency %s",
                    user_id,
                    agency_id,
                )


async def _check_approval_pending(db: AsyncSession) -> None:
    """Digests unlocked, completed entries older than _APPROVAL_PENDING_DAYS
    to users who can approve/lock them (TIME_ENTRY_APPROVE)."""
    cutoff = datetime.now(UTC) - timedelta(days=_APPROVAL_PENDING_DAYS)

    agency_rows = await db.execute(
        select(TimeEntry.agency_id)
        .where(
            TimeEntry.deleted_at.is_(None),
            TimeEntry.locked.is_(False),
            TimeEntry.ended_at.is_not(None),
            TimeEntry.started_at <= cutoff,
        )
        .distinct()
    )
    agency_ids = [row[0] for row in agency_rows]

    dispatcher = NotificationDispatcher(db)
    for agency_id in agency_ids:
        count_result = await db.execute(
            select(func.count())
            .select_from(TimeEntry)
            .where(
                TimeEntry.agency_id == agency_id,
                TimeEntry.deleted_at.is_(None),
                TimeEntry.locked.is_(False),
                TimeEntry.ended_at.is_not(None),
                TimeEntry.started_at <= cutoff,
            )
        )
        pending_count = count_result.scalar_one() or 0
        if pending_count == 0:
            continue

        dedup_key = f"{agency_id}:{utc_today().isoformat()}"
        if await _already_notified(
            db, NotificationEventType.TIME_ENTRY_APPROVAL_PENDING.value, "dedup_key", dedup_key
        ):
            continue

        approver_rows = await db.execute(
            select(AgencyMember.user_id, AgencyMember.role).where(
                AgencyMember.agency_id == agency_id,
                AgencyMember.deleted_at.is_(None),
                AgencyMember.status == "active",
            )
        )
        approver_ids = [
            row.user_id
            for row in approver_rows
            if Permission.TIME_ENTRY_APPROVE in get_permissions_for_agency_role(row.role)
        ]
        if not approver_ids:
            continue

        try:
            await dispatcher.emit(
                NotificationEventType.TIME_ENTRY_APPROVAL_PENDING.value,
                payload={
                    "dedup_key": dedup_key,
                    "pending_count": pending_count,
                    "summary": f"{pending_count} zaman kaydı onay bekliyor.",
                },
                agency_id=agency_id,
                brand_id=None,
                actor_user_id=None,
                recipient_ids=approver_ids,
            )
            await db.commit()
        except Exception:
            await db.rollback()
            log.exception("Failed to send TIME_ENTRY_APPROVAL_PENDING for agency %s", agency_id)


async def run_time_tracking_checks() -> None:
    """Runs all four time-tracking notification checks against a single
    fresh session, each independently wrapped so one check's failure never
    blocks the others."""
    async with AsyncSessionLocal() as db:
        for check in (
            _check_long_running_timers,
            _check_still_running_eod,
            _check_missing_timesheets,
            _check_approval_pending,
        ):
            try:
                await check(db)
            except Exception:
                await db.rollback()
                log.exception("Unexpected error in time tracking check %s", check.__name__)


async def _scheduler_loop() -> None:
    """Runs the time tracking checks once per hour."""
    while True:
        try:
            await run_time_tracking_checks()
        except Exception:
            log.exception("Unexpected error in time tracking scheduler")
        await asyncio.sleep(60 * 60)


def start_time_tracking_scheduler() -> asyncio.Task[None]:
    """Schedule the time tracking notification loop as a background asyncio task."""
    return asyncio.create_task(_scheduler_loop(), name="time_tracking_scheduler")
