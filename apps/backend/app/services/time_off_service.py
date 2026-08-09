"""TimeOffService: request/approve/reject leave, with the all-day
UTC-boundary math that keeps a full-day leave from shifting by a day when
viewed in a different timezone.

For `all_day=True` requests, the raw `start_at`/`end_at` sent by the caller
are treated only as "which calendar dates, expressed in the user's
WorkSchedule timezone, are being requested off" — never as literal UTC
instants. The stored boundaries are the UTC instant of local midnight on the
first day through the UTC instant of local midnight on the day *after* the
last day (an exclusive end boundary). Converting either boundary back into
the same IANA zone always lands exactly on a local midnight, so no viewer
timezone can make the leave appear to start or end a day earlier/later than
intended.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import NotificationEventType, TimeOffStatus
from app.models.time_off import TimeOff
from app.repositories.time_off import TimeOffRepository
from app.repositories.work_allocation import WorkAllocationRepository
from app.repositories.work_schedule import WorkScheduleRepository
from app.schemas.time_off import TimeOffCreate, TimeOffReject
from app.services.notification_dispatcher import NotificationDispatcher

_DEFAULT_TIMEZONE = "Europe/Istanbul"


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def compute_all_day_utc_bounds(
    start_at: datetime, end_at: datetime, timezone: str
) -> tuple[datetime, datetime]:
    """Given a caller-supplied [start_at, end_at] and an IANA timezone,
    returns the UTC instant of local midnight on `start_at`'s calendar date
    through the UTC instant of local midnight on the day *after* `end_at`'s
    calendar date. Pure function, unit-testable independent of the DB."""
    tz = ZoneInfo(timezone)
    start_local_date = _as_aware_utc(start_at).astimezone(tz).date()
    end_local_date = _as_aware_utc(end_at).astimezone(tz).date()
    if end_local_date < start_local_date:
        end_local_date = start_local_date

    start_utc = datetime.combine(start_local_date, time.min, tzinfo=tz).astimezone(UTC)
    end_utc = datetime.combine(end_local_date + timedelta(days=1), time.min, tzinfo=tz).astimezone(
        UTC
    )
    return start_utc, end_utc


class TimeOffService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = TimeOffRepository(db)
        self._schedule_repo = WorkScheduleRepository(db)
        self._allocation_repo = WorkAllocationRepository(db)

    async def _resolve_boundaries(
        self, agency_id: uuid.UUID, data: TimeOffCreate
    ) -> tuple[datetime, datetime]:
        if not data.all_day:
            return _as_aware_utc(data.start_at), _as_aware_utc(data.end_at)

        schedule = await self._schedule_repo.get_active_for_user(agency_id, data.user_id)
        timezone = schedule.timezone if schedule is not None else _DEFAULT_TIMEZONE
        return compute_all_day_utc_bounds(data.start_at, data.end_at, timezone)

    async def _has_overlapping_allocations(
        self,
        agency_id: uuid.UUID,
        user_id: uuid.UUID,
        start_at: datetime,
        end_at: datetime,
    ) -> bool:
        allocations = await self._allocation_repo.list_for_user(
            agency_id, user_id, start=start_at.date(), end=end_at.date()
        )
        return len(allocations) > 0

    async def request(self, agency_id: uuid.UUID, data: TimeOffCreate) -> tuple[TimeOff, bool]:
        """Creates a `requested` leave. Returns (entry, allocation_warning) —
        the warning is a non-blocking signal that the user already has
        WorkAllocation rows overlapping the requested range."""
        start_at, end_at = await self._resolve_boundaries(agency_id, data)

        obj = await self._repo.create(
            {
                "agency_id": agency_id,
                "user_id": data.user_id,
                "start_at": start_at,
                "end_at": end_at,
                "all_day": data.all_day,
                "type": data.type,
                "status": TimeOffStatus.REQUESTED.value,
                "notes": data.notes,
            }
        )
        await self._db.commit()
        await self._db.refresh(obj)

        allocation_warning = await self._has_overlapping_allocations(
            agency_id, data.user_id, start_at, end_at
        )
        return obj, allocation_warning

    async def approve(
        self, agency_id: uuid.UUID, time_off_id: uuid.UUID, approved_by_id: uuid.UUID
    ) -> tuple[TimeOff, bool]:
        obj = await self._repo.get_by_id(time_off_id, agency_id)
        if obj is None:
            raise NotFoundError("İzin talebi", str(time_off_id))
        if obj.status != TimeOffStatus.REQUESTED.value:
            raise ConflictError("Yalnızca beklemedeki izin talepleri onaylanabilir")

        updated = await self._repo.update(
            obj,
            {
                "status": TimeOffStatus.APPROVED.value,
                "approved_by_id": approved_by_id,
                "approved_at": datetime.now(UTC),
            },
        )
        await self._db.commit()
        await self._db.refresh(updated)

        await NotificationDispatcher(self._db).emit(
            NotificationEventType.TIME_OFF_APPROVED.value,
            payload={
                "time_off_id": str(updated.id),
                "type": updated.type,
                "start_at": updated.start_at.isoformat(),
                "end_at": updated.end_at.isoformat(),
                "summary": "İzin talebiniz onaylandı.",
            },
            agency_id=agency_id,
            actor_user_id=approved_by_id,
            recipient_ids=[updated.user_id],
        )
        await self._db.commit()

        allocation_warning = await self._has_overlapping_allocations(
            agency_id, updated.user_id, updated.start_at, updated.end_at
        )
        return updated, allocation_warning

    async def reject(
        self,
        agency_id: uuid.UUID,
        time_off_id: uuid.UUID,
        approved_by_id: uuid.UUID,
        data: TimeOffReject,
    ) -> TimeOff:
        obj = await self._repo.get_by_id(time_off_id, agency_id)
        if obj is None:
            raise NotFoundError("İzin talebi", str(time_off_id))
        if obj.status != TimeOffStatus.REQUESTED.value:
            raise ConflictError("Yalnızca beklemedeki izin talepleri reddedilebilir")

        update_data: dict = {
            "status": TimeOffStatus.REJECTED.value,
            "approved_by_id": approved_by_id,
            "approved_at": datetime.now(UTC),
        }
        if data.notes:
            update_data["notes"] = data.notes

        updated = await self._repo.update(obj, update_data)
        await self._db.commit()
        await self._db.refresh(updated)

        await NotificationDispatcher(self._db).emit(
            NotificationEventType.TIME_OFF_REJECTED.value,
            payload={
                "time_off_id": str(updated.id),
                "type": updated.type,
                "start_at": updated.start_at.isoformat(),
                "end_at": updated.end_at.isoformat(),
                "summary": "İzin talebiniz reddedildi.",
            },
            agency_id=agency_id,
            actor_user_id=approved_by_id,
            recipient_ids=[updated.user_id],
        )
        await self._db.commit()

        return updated

    async def list_for_user(
        self,
        agency_id: uuid.UUID,
        user_id: uuid.UUID,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[TimeOff]:
        return await self._repo.list_for_user(agency_id, user_id, start, end)
