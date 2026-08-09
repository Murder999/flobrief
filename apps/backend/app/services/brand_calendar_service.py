"""Server-side merge of real CalendarItem rows and Brief-derived milestone dates
into a single, filterable brand-portal calendar feed.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brief import Brief, BriefAssignee
from app.models.calendar import CalendarItem, CalendarItemAssignee
from app.models.user import User

MILESTONE_LABELS: dict[str, str] = {
    "brief_start": "Brief Başlangıcı",
    "first_draft": "İlk Taslak",
    "brand_feedback": "Marka Geri Bildirimi",
    "approval_deadline": "Onay Son Tarihi",
    "final_delivery": "Nihai Teslim",
    "publish_date": "Yayın Tarihi",
}

_BRIEF_DATE_FIELD_TO_MILESTONE: dict[str, str] = {
    "start_date": "brief_start",
    "draft_date": "first_draft",
    "feedback_date": "brand_feedback",
    "deadline": "approval_deadline",
    "publish_date": "publish_date",
}


class BrandCalendarEntry(BaseModel):
    id: str
    kind: str  # "calendar_item" | "brief_milestone"
    event_type: str
    title: str
    entry_date: date
    entry_time: datetime | None = None
    priority: str
    status: str
    brief_id: uuid.UUID | None = None
    brief_title: str | None = None
    calendar_item_id: uuid.UUID | None = None
    assignee_ids: list[uuid.UUID] = []
    assignee_names: list[str] = []


def _parse_brief_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


async def _load_assignees_by_calendar_item(
    db: AsyncSession, item_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[tuple[uuid.UUID, str]]]:
    if not item_ids:
        return {}
    rows = (
        await db.execute(
            select(CalendarItemAssignee.calendar_item_id, User.id, User.full_name)
            .join(User, User.id == CalendarItemAssignee.user_id)
            .where(CalendarItemAssignee.calendar_item_id.in_(item_ids))
        )
    ).all()
    out: dict[uuid.UUID, list[tuple[uuid.UUID, str]]] = {}
    for cal_item_id, user_id, full_name in rows:
        out.setdefault(cal_item_id, []).append((user_id, full_name))
    return out


async def _load_assignees_by_brief(
    db: AsyncSession, brief_ids: set[uuid.UUID]
) -> dict[uuid.UUID, list[tuple[uuid.UUID, str]]]:
    if not brief_ids:
        return {}
    rows = (
        await db.execute(
            select(BriefAssignee.brief_id, User.id, User.full_name)
            .join(User, User.id == BriefAssignee.user_id)
            .where(BriefAssignee.brief_id.in_(brief_ids))
        )
    ).all()
    out: dict[uuid.UUID, list[tuple[uuid.UUID, str]]] = {}
    for b_id, user_id, full_name in rows:
        out.setdefault(b_id, []).append((user_id, full_name))
    return out


async def build_brand_calendar_agenda(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
    event_type: str | None = None,
    brief_id: uuid.UUID | None = None,
    assignee_id: uuid.UUID | None = None,
    priority: str | None = None,
) -> list[BrandCalendarEntry]:
    """Merges real CalendarItem rows with Brief milestone dates for one brand.

    Both sources are queried fresh (no client-side merging) so filtering and
    grouping stay consistent regardless of which source an entry came from.
    """
    entries: list[BrandCalendarEntry] = []

    item_q = select(CalendarItem).where(
        CalendarItem.brand_id == brand_id,
        CalendarItem.deleted_at.is_(None),
    )
    if brief_id:
        item_q = item_q.where(CalendarItem.brief_id == brief_id)
    items = (await db.execute(item_q)).scalars().all()

    assignees_by_item = await _load_assignees_by_calendar_item(db, [i.id for i in items])
    brief_ids_referenced = {i.brief_id for i in items if i.brief_id}

    for item in items:
        entry_dt = item.publish_at or item.due_at
        if entry_dt is None:
            continue
        entry_d = entry_dt.date()
        if date_from and entry_d < date_from:
            continue
        if date_to and entry_d > date_to:
            continue
        pairs = assignees_by_item.get(item.id, [])
        entries.append(
            BrandCalendarEntry(
                id=f"item:{item.id}",
                kind="calendar_item",
                event_type=item.milestone_type or item.item_type,
                title=item.title,
                entry_date=entry_d,
                entry_time=entry_dt,
                priority=item.priority,
                status=item.status,
                brief_id=item.brief_id,
                calendar_item_id=item.id,
                assignee_ids=[p[0] for p in pairs],
                assignee_names=[p[1] for p in pairs],
            )
        )

    brief_q = select(Brief).where(Brief.brand_id == brand_id, Brief.deleted_at.is_(None))
    if brief_id:
        brief_q = brief_q.where(Brief.id == brief_id)
    briefs = (await db.execute(brief_q)).scalars().all()

    brief_ids_all = {b.id for b in briefs} | brief_ids_referenced
    assignees_by_brief = await _load_assignees_by_brief(db, brief_ids_all)

    if brief_ids_referenced:
        titles = dict(
            (
                await db.execute(
                    select(Brief.id, Brief.title).where(Brief.id.in_(brief_ids_referenced))
                )
            ).all()
        )
        for entry in entries:
            if entry.brief_id:
                entry.brief_title = titles.get(entry.brief_id)
                if not entry.assignee_ids:
                    pairs = assignees_by_brief.get(entry.brief_id, [])
                    entry.assignee_ids = [p[0] for p in pairs]
                    entry.assignee_names = [p[1] for p in pairs]

    for brief in briefs:
        pairs = assignees_by_brief.get(brief.id, [])
        for field_name, milestone_type in _BRIEF_DATE_FIELD_TO_MILESTONE.items():
            entry_d = _parse_brief_date(getattr(brief, field_name))
            if entry_d is None:
                continue
            if date_from and entry_d < date_from:
                continue
            if date_to and entry_d > date_to:
                continue
            entries.append(
                BrandCalendarEntry(
                    id=f"milestone:{brief.id}:{milestone_type}",
                    kind="brief_milestone",
                    event_type=milestone_type,
                    title=f"{brief.title} — {MILESTONE_LABELS[milestone_type]}",
                    entry_date=entry_d,
                    entry_time=None,
                    priority=brief.priority,
                    status=brief.status,
                    brief_id=brief.id,
                    brief_title=brief.title,
                    assignee_ids=[p[0] for p in pairs],
                    assignee_names=[p[1] for p in pairs],
                )
            )

    return filter_and_sort_entries(
        entries,
        status=status,
        event_type=event_type,
        priority=priority,
        assignee_id=assignee_id,
    )


def filter_and_sort_entries(
    entries: list[BrandCalendarEntry],
    *,
    status: str | None = None,
    event_type: str | None = None,
    priority: str | None = None,
    assignee_id: uuid.UUID | None = None,
) -> list[BrandCalendarEntry]:
    """Pure filter/sort step, split out from the DB query so it's unit-testable
    without a live database.
    """
    if status:
        entries = [e for e in entries if e.status == status]
    if event_type:
        entries = [e for e in entries if e.event_type == event_type]
    if priority:
        entries = [e for e in entries if e.priority == priority]
    if assignee_id:
        entries = [e for e in entries if assignee_id in e.assignee_ids]

    return sorted(entries, key=lambda e: (e.entry_date, e.entry_time or datetime.min))
