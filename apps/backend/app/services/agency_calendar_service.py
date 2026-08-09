"""Server-side merge of the agency's operational calendar sources — real
CalendarItem rows (including agency-internal ones with no brand), Brief
milestone dates, and Deliverable lifecycle events — into a single, filterable
agency-portal calendar feed.

Mirrors the merge approach in ``brand_calendar_service.py``, but scoped to
the whole agency (all brands + agency-internal) rather than one brand.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.models.brief import Brief, BriefAssignee
from app.models.calendar import CalendarItem, CalendarItemAssignee
from app.models.deliverable import Deliverable
from app.models.user import User

MILESTONE_LABELS: dict[str, str] = {
    "brief_start": "Brief Başlangıcı",
    "first_draft": "İlk Taslak",
    "brand_feedback": "Marka Geri Bildirimi",
    "approval_deadline": "Onay Son Tarihi",
    "final_delivery": "Nihai Teslim",
    "publish_date": "Yayın Tarihi",
    "deliverable_submitted": "Teslim Gönderildi",
    "revision_requested": "Revizyon İstendi",
}

_BRIEF_DATE_FIELD_TO_MILESTONE: dict[str, str] = {
    "start_date": "brief_start",
    "draft_date": "first_draft",
    "feedback_date": "brand_feedback",
    "deadline": "approval_deadline",
    "publish_date": "publish_date",
}

# Statuses past which a date-in-the-past no longer counts as "overdue".
_TERMINAL_BRIEF_STATUSES = {"approved", "completed", "archived", "rejected", "cancelled"}
_TERMINAL_ITEM_STATUSES = {"published", "cancelled"}
_TERMINAL_DELIVERABLE_STATUSES = {"approved", "rejected", "archived"}


class AgencyCalendarEntry(BaseModel):
    id: str
    source_type: str  # manual | brief_start | first_draft | brand_feedback |
    # approval_deadline | publish_date | deliverable_submitted | revision_requested
    calendar_item_id: uuid.UUID | None = None
    agency_id: uuid.UUID
    brand_id: uuid.UUID | None = None
    brand_name: str | None = None
    brand_logo_url: str | None = None
    title: str
    description: str | None = None
    item_type: str
    platform: str | None = None
    status: str
    priority: str
    milestone_type: str | None = None
    publish_at: datetime | None = None
    due_at: datetime | None = None
    all_day: bool = False
    brief_id: uuid.UUID | None = None
    brief_title: str | None = None
    deliverable_id: uuid.UUID | None = None
    assignee_ids: list[uuid.UUID] = []
    assignee_names: list[str] = []
    is_overdue: bool = False
    editable: bool = False
    action_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


def _parse_brief_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _date_of(dt: datetime | None) -> date | None:
    if dt is None:
        return None
    return dt.date()


def _is_overdue(entry_date: date | None, status: str, terminal: set[str]) -> bool:
    if entry_date is None:
        return False
    return entry_date < datetime.now(UTC).date() and status not in terminal


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


async def build_agency_calendar_agenda(
    db: AsyncSession,
    agency_id: uuid.UUID,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    brand_id: uuid.UUID | None = None,
    internal_only: bool = False,
    status: str | None = None,
    event_type: str | None = None,
    assignee_id: uuid.UUID | None = None,
    priority: str | None = None,
) -> list[AgencyCalendarEntry]:
    """Merges real CalendarItem rows with Brief milestones and Deliverable
    lifecycle events for one agency (optionally narrowed to one brand or to
    agency-internal-only entries).

    All three sources are queried fresh (no client-side caching) so filtering
    stays consistent regardless of which source an entry came from.
    """
    entries: list[AgencyCalendarEntry] = []

    # ── Real CalendarItem rows (manual entries + legacy brief-deadline sync) ──
    item_q = (
        select(CalendarItem, Brand.name, Brand.logo_url)
        .outerjoin(Brand, Brand.id == CalendarItem.brand_id)
        .where(CalendarItem.agency_id == agency_id, CalendarItem.deleted_at.is_(None))
    )
    if internal_only:
        item_q = item_q.where(CalendarItem.brand_id.is_(None))
    elif brand_id:
        item_q = item_q.where(CalendarItem.brand_id == brand_id)
    item_rows = (await db.execute(item_q)).all()
    items = [row[0] for row in item_rows]

    assignees_by_item = await _load_assignees_by_calendar_item(db, [i.id for i in items])
    # (brief_id, date) pairs already represented by a real CalendarItem — used to
    # dedup against the synthetic brief-milestone entries synthesized below, so a
    # brief deadline that already has a linked CalendarItem doesn't show twice.
    real_item_brief_dates: set[tuple[uuid.UUID, date]] = set()

    for item, b_name, b_logo in item_rows:
        entry_dt = item.publish_at or item.due_at
        entry_d = _date_of(entry_dt)
        if entry_d is not None and item.brief_id:
            real_item_brief_dates.add((item.brief_id, entry_d))
        if date_from and entry_d and entry_d < date_from:
            continue
        if date_to and entry_d and entry_d > date_to:
            continue
        pairs = assignees_by_item.get(item.id, [])
        entries.append(
            AgencyCalendarEntry(
                id=f"item:{item.id}",
                source_type=item.milestone_type or "manual",
                calendar_item_id=item.id,
                agency_id=item.agency_id,
                brand_id=item.brand_id,
                brand_name=b_name,
                brand_logo_url=b_logo,
                title=item.title,
                description=item.description,
                item_type=item.item_type,
                platform=item.platform,
                status=item.status,
                priority=item.priority,
                milestone_type=item.milestone_type,
                publish_at=item.publish_at,
                due_at=item.due_at,
                all_day=False,
                brief_id=item.brief_id,
                assignee_ids=[p[0] for p in pairs],
                assignee_names=[p[1] for p in pairs],
                is_overdue=_is_overdue(entry_d, item.status, _TERMINAL_ITEM_STATUSES),
                editable=True,
                action_url=f"/dashboard/briefs/{item.brief_id}" if item.brief_id else None,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )

    # ── Brief milestone dates (skipped for agency-internal-only view) ────────
    brief_ids_referenced = {i.brief_id for i in items if i.brief_id}
    briefs: list[Brief] = []
    brief_brand_names: dict[uuid.UUID | None, tuple[str | None, str | None]] = {}
    if not internal_only:
        brief_q = (
            select(Brief, Brand.name, Brand.logo_url)
            .outerjoin(Brand, Brand.id == Brief.brand_id)
            .where(Brief.agency_id == agency_id, Brief.deleted_at.is_(None))
        )
        if brand_id:
            brief_q = brief_q.where(Brief.brand_id == brand_id)
        brief_rows = (await db.execute(brief_q)).all()
        briefs = [row[0] for row in brief_rows]
        for brief, b_name, b_logo in brief_rows:
            brief_brand_names[brief.id] = (b_name, b_logo)

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
        b_name, b_logo = brief_brand_names.get(brief.id, (None, None))
        for field_name, milestone_type in _BRIEF_DATE_FIELD_TO_MILESTONE.items():
            entry_d = _parse_brief_date(getattr(brief, field_name))
            if entry_d is None:
                continue
            if (brief.id, entry_d) in real_item_brief_dates:
                continue  # already represented by a real, editable CalendarItem
            if date_from and entry_d < date_from:
                continue
            if date_to and entry_d > date_to:
                continue
            entry_dt = datetime.combine(entry_d, datetime.min.time()).replace(hour=12, tzinfo=UTC)
            entries.append(
                AgencyCalendarEntry(
                    id=f"milestone:{brief.id}:{milestone_type}",
                    source_type=milestone_type,
                    agency_id=agency_id,
                    brand_id=brief.brand_id,
                    brand_name=b_name,
                    brand_logo_url=b_logo,
                    title=f"{brief.title} — {MILESTONE_LABELS[milestone_type]}",
                    item_type="brief",
                    status=brief.status,
                    priority=brief.priority,
                    milestone_type=milestone_type,
                    publish_at=entry_dt,
                    all_day=True,
                    brief_id=brief.id,
                    brief_title=brief.title,
                    assignee_ids=[p[0] for p in pairs],
                    assignee_names=[p[1] for p in pairs],
                    is_overdue=_is_overdue(entry_d, brief.status, _TERMINAL_BRIEF_STATUSES),
                    editable=False,
                    action_url=f"/dashboard/briefs/{brief.id}",
                )
            )

    # ── Deliverable lifecycle events (skipped for agency-internal-only view) ─
    if not internal_only:
        deliv_q = (
            select(Deliverable, Brief.title, Brief.brand_id, Brand.name, Brand.logo_url)
            .join(Brief, Brief.id == Deliverable.brief_id)
            .outerjoin(Brand, Brand.id == Brief.brand_id)
            .where(Deliverable.agency_id == agency_id, Deliverable.deleted_at.is_(None))
        )
        if brand_id:
            deliv_q = deliv_q.where(Brief.brand_id == brand_id)
        deliv_rows = (await db.execute(deliv_q)).all()

        for deliverable, brief_title, d_brand_id, b_name, b_logo in deliv_rows:
            if deliverable.submitted_at is not None:
                entry_d = _date_of(deliverable.submitted_at)
                if not ((date_from and entry_d < date_from) or (date_to and entry_d > date_to)):
                    entries.append(
                        AgencyCalendarEntry(
                            id=f"deliverable:{deliverable.id}:submitted",
                            source_type="deliverable_submitted",
                            agency_id=agency_id,
                            brand_id=d_brand_id,
                            brand_name=b_name,
                            brand_logo_url=b_logo,
                            title=f"{deliverable.title} — Teslim Gönderildi",
                            item_type="deliverable",
                            status=deliverable.status,
                            priority="normal",
                            milestone_type="deliverable_submitted",
                            publish_at=deliverable.submitted_at,
                            all_day=False,
                            brief_id=deliverable.brief_id,
                            brief_title=brief_title,
                            deliverable_id=deliverable.id,
                            is_overdue=False,
                            editable=False,
                            action_url=f"/dashboard/briefs/{deliverable.brief_id}",
                        )
                    )
            if deliverable.status == "revision_requested":
                entry_dt = deliverable.updated_at
                entry_d = _date_of(entry_dt)
                if not ((date_from and entry_d < date_from) or (date_to and entry_d > date_to)):
                    entries.append(
                        AgencyCalendarEntry(
                            id=f"deliverable:{deliverable.id}:revision",
                            source_type="revision_requested",
                            agency_id=agency_id,
                            brand_id=d_brand_id,
                            brand_name=b_name,
                            brand_logo_url=b_logo,
                            title=f"{deliverable.title} — Revizyon İstendi",
                            item_type="deliverable",
                            status=deliverable.status,
                            priority="high",
                            milestone_type="revision_requested",
                            publish_at=entry_dt,
                            all_day=False,
                            brief_id=deliverable.brief_id,
                            brief_title=brief_title,
                            deliverable_id=deliverable.id,
                            is_overdue=_is_overdue(
                                entry_d, deliverable.status, _TERMINAL_DELIVERABLE_STATUSES
                            ),
                            editable=False,
                            action_url=f"/dashboard/briefs/{deliverable.brief_id}",
                        )
                    )

    return filter_and_sort_agency_entries(
        entries,
        status=status,
        event_type=event_type,
        priority=priority,
        assignee_id=assignee_id,
    )


def filter_and_sort_agency_entries(
    entries: list[AgencyCalendarEntry],
    *,
    status: str | None = None,
    event_type: str | None = None,
    priority: str | None = None,
    assignee_id: uuid.UUID | None = None,
) -> list[AgencyCalendarEntry]:
    """Pure filter/sort step, split out from the DB query so it's unit-testable
    without a live database.
    """
    if status:
        entries = [e for e in entries if e.status == status]
    if event_type:
        entries = [e for e in entries if e.source_type == event_type]
    if priority:
        entries = [e for e in entries if e.priority == priority]
    if assignee_id:
        entries = [e for e in entries if assignee_id in e.assignee_ids]

    def _sort_key(e: AgencyCalendarEntry) -> datetime:
        return e.publish_at or e.due_at or datetime.min.replace(tzinfo=UTC)

    return sorted(entries, key=_sort_key)
