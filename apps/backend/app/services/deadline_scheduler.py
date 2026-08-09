"""Deadline reminder scheduler: daily background task that emits
CALENDAR_ITEM_DUE notifications for briefs due within 3 days."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_today
from app.db.session import AsyncSessionLocal
from app.models.brief import Brief
from app.models.enums import BriefStatus, NotificationEventType
from app.models.notification import NotificationEvent
from app.services.notification_dispatcher import NotificationDispatcher

log = logging.getLogger(__name__)

_LOOKAHEAD_DAYS = 3
_DEDUP_HOURS = 23  # suppress repeat reminders within 23 h

# Terminal/resolved statuses — a brief in any of these no longer needs a
# due-soon or overdue reminder (it's already approved/completed/archived/
# rejected, so a deadline reminder would be noise, not signal).
_REMINDER_EXCLUDED_STATUSES = {
    BriefStatus.ARCHIVED.value,
    BriefStatus.APPROVED.value,
    BriefStatus.COMPLETED.value,
    BriefStatus.REJECTED.value,
}


async def _already_notified(db: AsyncSession, event_type: str, brief_id: str) -> bool:
    """Return True if `event_type` was emitted for this brief in the last
    _DEDUP_HOURS hours — the same "keep reminding daily, never twice within
    the window" shape used for every other reminder scheduler in this repo."""
    cutoff = datetime.now(UTC) - timedelta(hours=_DEDUP_HOURS)
    stmt = (
        select(NotificationEvent.id)
        .where(
            NotificationEvent.event_type == event_type,
            NotificationEvent.created_at >= cutoff,
            # payload JSONB field lookup
            func.jsonb_extract_path_text(cast(NotificationEvent.payload, JSONB), "brief_id")
            == brief_id,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def run_deadline_check() -> None:
    """Query active briefs due within _LOOKAHEAD_DAYS and emit reminders."""
    today = utc_today()
    window_start = today.isoformat()
    window_end = (today + timedelta(days=_LOOKAHEAD_DAYS)).isoformat()

    async with AsyncSessionLocal() as db:
        stmt = select(Brief).where(
            Brief.deadline >= window_start,
            Brief.deadline <= window_end,
            Brief.deleted_at.is_(None),
            Brief.status.not_in(_REMINDER_EXCLUDED_STATUSES),
        )
        result = await db.execute(stmt)
        briefs = result.scalars().all()

        dispatcher = NotificationDispatcher(db)
        for brief in briefs:
            bid_str = str(brief.id)
            if await _already_notified(db, NotificationEventType.CALENDAR_ITEM_DUE.value, bid_str):
                continue

            try:
                await dispatcher.emit(
                    NotificationEventType.CALENDAR_ITEM_DUE.value,
                    payload={
                        "brief_id": bid_str,
                        "brief_title": brief.title,
                        "deadline": brief.deadline,
                        "summary": f"Teslim tarihi yaklaşıyor: {brief.title} ({brief.deadline})",
                    },
                    agency_id=brief.agency_id,
                    brand_id=brief.brand_id,
                    actor_user_id=None,
                )
                await db.commit()
                log.info("Deadline reminder sent for brief %s", bid_str)
            except Exception:
                await db.rollback()
                log.exception("Failed to send deadline reminder for brief %s", bid_str)


async def run_overdue_check() -> None:
    """Query active briefs whose deadline has already passed and emit a
    BRIEF_OVERDUE reminder. Re-fires daily (same _DEDUP_HOURS window as
    run_deadline_check) until the brief is resolved/archived — it does not
    escalate or accumulate, matching INVOICE_OVERDUE's "keep reminding until
    resolved" shape in finance_capacity_scheduler."""
    today = utc_today()
    window_end = today.isoformat()

    async with AsyncSessionLocal() as db:
        stmt = select(Brief).where(
            Brief.deadline.is_not(None),
            Brief.deadline < window_end,
            Brief.deleted_at.is_(None),
            Brief.status.not_in(_REMINDER_EXCLUDED_STATUSES),
        )
        result = await db.execute(stmt)
        briefs = result.scalars().all()

        dispatcher = NotificationDispatcher(db)
        for brief in briefs:
            bid_str = str(brief.id)
            if await _already_notified(db, NotificationEventType.BRIEF_OVERDUE.value, bid_str):
                continue

            try:
                await dispatcher.emit(
                    NotificationEventType.BRIEF_OVERDUE.value,
                    payload={
                        "brief_id": bid_str,
                        "brief_title": brief.title,
                        "deadline": brief.deadline,
                        "summary": f"Teslim tarihi geçti: {brief.title} ({brief.deadline})",
                    },
                    agency_id=brief.agency_id,
                    brand_id=brief.brand_id,
                    actor_user_id=None,
                )
                await db.commit()
                log.info("Overdue reminder sent for brief %s", bid_str)
            except Exception:
                await db.rollback()
                log.exception("Failed to send overdue reminder for brief %s", bid_str)


async def run_deadline_and_overdue_checks() -> None:
    """Runs both brief-deadline checks against independent sessions, each
    isolated so one failing doesn't block the other (mirrors
    run_finance_capacity_checks)."""
    for check in (run_deadline_check, run_overdue_check):
        try:
            await check()
        except Exception:
            log.exception("Unexpected error in deadline/overdue check %s", check.__name__)


async def _scheduler_loop() -> None:
    """Run deadline + overdue checks once per day, starting at the next
    midnight UTC."""
    now = datetime.now(UTC)
    tomorrow_midnight = datetime(now.year, now.month, now.day, tzinfo=UTC) + timedelta(days=1)
    initial_sleep = (tomorrow_midnight - now).total_seconds()
    await asyncio.sleep(initial_sleep)

    while True:
        try:
            await run_deadline_and_overdue_checks()
        except Exception:
            log.exception("Unexpected error in deadline scheduler")
        # Wait 24 h before next run
        await asyncio.sleep(60 * 60 * 24)


def start_deadline_scheduler() -> asyncio.Task[None]:
    """Schedule the deadline reminder loop as a background asyncio task."""
    return asyncio.create_task(_scheduler_loop(), name="deadline_scheduler")
