"""TimeReportService: real aggregates only — weekly timesheets, team
rollups, per-brand summaries, missing-timesheet detection, and CSV export.
Every number here is computed on read from real TimeEntry rows; nothing is
stored or fabricated."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission, get_permissions_for_agency_role
from app.models.agency_member import AgencyMember
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.repositories.time_entry import TimeEntryRepository
from app.schemas.time_entry import TimeEntryRead
from app.schemas.time_report import (
    BrandTimeSummary,
    CategoryBreakdown,
    MissingTimesheetEntry,
    MissingTimesheetResponse,
    TeamTimeReportResponse,
    UserTimeSummary,
    WeeklyTimesheetResponse,
)


def _day_range_to_utc_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=UTC)
    end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=UTC)
    return start_dt, end_dt


def _hours(entries: list[TimeEntry]) -> float:
    return round(sum(e.duration_seconds or 0 for e in entries) / 3600, 2)


def _category_breakdown(entries: list[TimeEntry]) -> list[CategoryBreakdown]:
    buckets: dict[str, list[float | int]] = {}
    for e in entries:
        if e.duration_seconds is None:
            continue
        bucket = buckets.setdefault(e.category, [0.0, 0])
        bucket[0] += e.duration_seconds / 3600
        bucket[1] += 1
    return [
        CategoryBreakdown(category=cat, hours=round(hours, 2), entry_count=count)
        for cat, (hours, count) in sorted(buckets.items())
    ]


class TimeReportService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = TimeEntryRepository(db)

    async def weekly_timesheet(
        self,
        agency_id: uuid.UUID,
        user_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> WeeklyTimesheetResponse:
        start_dt, end_dt = _day_range_to_utc_bounds(start_date, end_date)
        entries = await self._repo.list_for_user(user_id, agency_id, start_dt, end_dt)
        finalized = [e for e in entries if e.duration_seconds is not None]

        by_day: dict[str, float] = {}
        for e in finalized:
            key = e.started_at.date().isoformat()
            by_day[key] = round(by_day.get(key, 0.0) + e.duration_seconds / 3600, 2)

        billable = [e for e in finalized if e.billable]

        return WeeklyTimesheetResponse(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            entries=[TimeEntryRead.model_validate(e) for e in entries],
            total_hours=_hours(finalized),
            billable_hours=_hours(billable),
            by_day=by_day,
        )

    async def team_report(
        self,
        agency_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> TeamTimeReportResponse:
        start_dt, end_dt = _day_range_to_utc_bounds(start_date, end_date)
        entries = await self._repo.list_for_agency(agency_id, start_dt, end_dt)
        finalized = [e for e in entries if e.duration_seconds is not None]

        by_user: dict[uuid.UUID, list[TimeEntry]] = {}
        for e in finalized:
            by_user.setdefault(e.user_id, []).append(e)

        user_ids = list(by_user.keys())
        names: dict[uuid.UUID, str] = {}
        if user_ids:
            name_stmt = select(User.id, User.full_name).where(User.id.in_(user_ids))
            result = await self._db.execute(name_stmt)
            names = {row[0]: row[1] for row in result.all()}

        users = [
            UserTimeSummary(
                user_id=uid,
                user_name=names.get(uid, "Bilinmeyen Kullanıcı"),
                total_hours=_hours(user_entries),
                billable_hours=_hours([e for e in user_entries if e.billable]),
                entry_count=len(user_entries),
            )
            for uid, user_entries in sorted(
                by_user.items(), key=lambda kv: _hours(kv[1]), reverse=True
            )
        ]

        billable_all = [e for e in finalized if e.billable]
        return TeamTimeReportResponse(
            start_date=start_date,
            end_date=end_date,
            users=users,
            total_hours=_hours(finalized),
            billable_hours=_hours(billable_all),
        )

    async def brand_summary(
        self,
        agency_id: uuid.UUID,
        brand_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> BrandTimeSummary:
        start_dt = end_dt = None
        if start_date is not None and end_date is not None:
            start_dt, end_dt = _day_range_to_utc_bounds(start_date, end_date)

        entries = await self._repo.list_for_brand(brand_id, agency_id, start_dt, end_dt)
        finalized = [e for e in entries if e.duration_seconds is not None]
        billable = [e for e in finalized if e.billable]
        brief_ids = {e.brief_id for e in finalized if e.brief_id is not None}

        return BrandTimeSummary(
            brand_id=brand_id,
            total_hours=_hours(finalized),
            billable_hours=_hours(billable),
            non_billable_hours=round(_hours(finalized) - _hours(billable), 2),
            brief_count=len(brief_ids),
            entry_count=len(finalized),
            category_breakdown=_category_breakdown(finalized),
        )

    async def missing_timesheet(
        self,
        agency_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> MissingTimesheetResponse:
        """Any active member with TIME_ENTRY_LOG who logged zero entries for
        a completed calendar day. No holiday/weekend calendar exists to
        exclude non-workdays — a deliberate Part-1 simplification. Only days
        strictly before today are considered "completed"."""
        today = datetime.now(UTC).date()
        effective_end = min(end_date, today - timedelta(days=1))
        if effective_end < start_date:
            return MissingTimesheetResponse(start_date=start_date, end_date=end_date, missing=[])

        member_rows = await self._db.execute(
            select(AgencyMember.user_id, AgencyMember.role, User.full_name)
            .join(User, User.id == AgencyMember.user_id)
            .where(
                AgencyMember.agency_id == agency_id,
                AgencyMember.deleted_at.is_(None),
                AgencyMember.status == "active",
                User.deleted_at.is_(None),
                User.is_active.is_(True),
            )
        )
        loggers = {
            row.user_id: row.full_name
            for row in member_rows
            if Permission.TIME_ENTRY_LOG in get_permissions_for_agency_role(row.role)
        }
        if not loggers:
            return MissingTimesheetResponse(start_date=start_date, end_date=end_date, missing=[])

        start_dt, end_dt = _day_range_to_utc_bounds(start_date, effective_end)
        entries = await self._repo.list_for_agency(agency_id, start_dt, end_dt)

        logged_by_day: dict[date, set[uuid.UUID]] = {}
        for e in entries:
            logged_by_day.setdefault(e.started_at.date(), set()).add(e.user_id)

        missing: list[MissingTimesheetEntry] = []
        current = start_date
        while current <= effective_end:
            logged_today = logged_by_day.get(current, set())
            for uid, name in loggers.items():
                if uid not in logged_today:
                    missing.append(
                        MissingTimesheetEntry(user_id=uid, user_name=name, missing_date=current)
                    )
            current += timedelta(days=1)

        return MissingTimesheetResponse(start_date=start_date, end_date=end_date, missing=missing)

    async def export_csv(
        self,
        agency_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> bytes:
        start_dt, end_dt = _day_range_to_utc_bounds(start_date, end_date)
        entries = await self._repo.list_for_agency(agency_id, start_dt, end_dt)

        user_ids = {e.user_id for e in entries}
        names: dict[uuid.UUID, str] = {}
        if user_ids:
            result = await self._db.execute(
                select(User.id, User.full_name).where(User.id.in_(user_ids))
            )
            names = {row[0]: row[1] for row in result.all()}

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "date",
                "user",
                "brief_id",
                "brand_id",
                "category",
                "description",
                "duration_hours",
                "billable",
                "source",
                "locked",
            ]
        )
        for e in entries:
            writer.writerow(
                [
                    e.started_at.date().isoformat(),
                    names.get(e.user_id, str(e.user_id)),
                    str(e.brief_id) if e.brief_id else "",
                    str(e.brand_id) if e.brand_id else "",
                    e.category,
                    (e.description or "").replace("\n", " ").strip(),
                    round((e.duration_seconds or 0) / 3600, 2),
                    "evet" if e.billable else "hayır",
                    e.source,
                    "evet" if e.locked else "hayır",
                ]
            )
        return buffer.getvalue().encode("utf-8-sig")
