from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.work_schedule import WorkSchedule, WorkScheduleDay


class WorkScheduleRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_active_for_user(
        self, agency_id: uuid.UUID, user_id: uuid.UUID
    ) -> WorkSchedule | None:
        result = await self.db.execute(
            select(WorkSchedule).where(
                WorkSchedule.agency_id == agency_id,
                WorkSchedule.user_id == user_id,
                WorkSchedule.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, schedule_id: uuid.UUID, agency_id: uuid.UUID) -> WorkSchedule | None:
        result = await self.db.execute(
            select(WorkSchedule).where(
                WorkSchedule.id == schedule_id,
                WorkSchedule.agency_id == agency_id,
                WorkSchedule.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_days(self, work_schedule_id: uuid.UUID) -> list[WorkScheduleDay]:
        result = await self.db.execute(
            select(WorkScheduleDay)
            .where(
                WorkScheduleDay.work_schedule_id == work_schedule_id,
                WorkScheduleDay.deleted_at.is_(None),
            )
            .order_by(WorkScheduleDay.weekday.asc())
        )
        return list(result.scalars().all())

    async def create(self, data: dict) -> WorkSchedule:
        obj = WorkSchedule(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def add_days(
        self, work_schedule_id: uuid.UUID, days: list[dict]
    ) -> list[WorkScheduleDay]:
        objs = [WorkScheduleDay(work_schedule_id=work_schedule_id, **day) for day in days]
        self.db.add_all(objs)
        await self.db.flush()
        return objs

    async def soft_delete(self, schedule: WorkSchedule) -> None:
        schedule.soft_delete()
        await self.db.flush()
