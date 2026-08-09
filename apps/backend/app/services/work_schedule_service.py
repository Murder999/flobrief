"""WorkScheduleService: CRUD for a user's WorkSchedule+WorkScheduleDay
aggregate. Edits are always soft-delete-old + insert-new — never an in-place
mutation — so a capacity calculation for a past date range keeps using the
schedule that was actually active back then."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.work_schedule import WorkSchedule, WorkScheduleDay
from app.repositories.work_schedule import WorkScheduleRepository
from app.schemas.work_schedule import WorkScheduleCreate


class WorkScheduleService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = WorkScheduleRepository(db)

    async def get_active(
        self, agency_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[WorkSchedule, list[WorkScheduleDay]] | None:
        schedule = await self._repo.get_active_for_user(agency_id, user_id)
        if schedule is None:
            return None
        days = await self._repo.get_days(schedule.id)
        return schedule, days

    async def require_active(
        self, agency_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[WorkSchedule, list[WorkScheduleDay]]:
        result = await self.get_active(agency_id, user_id)
        if result is None:
            raise NotFoundError("Çalışma programı", str(user_id))
        return result

    async def upsert(
        self, agency_id: uuid.UUID, data: WorkScheduleCreate
    ) -> tuple[WorkSchedule, list[WorkScheduleDay]]:
        """Soft-deletes any existing active schedule for `data.user_id` and
        inserts a brand-new schedule+days aggregate. The old row's
        `deleted_at` is flushed before the new row is inserted, so the
        partial unique index (`uq_work_schedule_one_active_per_user`) never
        sees two live rows for the same (agency_id, user_id) at once."""
        existing = await self._repo.get_active_for_user(agency_id, data.user_id)
        if existing is not None:
            await self._repo.soft_delete(existing)

        schedule = await self._repo.create(
            {
                "agency_id": agency_id,
                "user_id": data.user_id,
                "timezone": data.timezone,
                "effective_from": data.effective_from,
            }
        )
        days = await self._repo.add_days(
            schedule.id,
            [day.model_dump() for day in data.days],
        )
        await self._db.commit()
        await self._db.refresh(schedule)
        return schedule, days
