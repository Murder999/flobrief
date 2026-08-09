from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.time_off import TimeOff


class TimeOffRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, time_off_id: uuid.UUID, agency_id: uuid.UUID) -> TimeOff | None:
        result = await self.db.execute(
            select(TimeOff).where(
                TimeOff.id == time_off_id,
                TimeOff.agency_id == agency_id,
                TimeOff.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        agency_id: uuid.UUID,
        user_id: uuid.UUID,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[TimeOff]:
        conditions = [
            TimeOff.agency_id == agency_id,
            TimeOff.user_id == user_id,
            TimeOff.deleted_at.is_(None),
        ]
        if start is not None:
            conditions.append(TimeOff.end_at >= start)
        if end is not None:
            conditions.append(TimeOff.start_at <= end)
        result = await self.db.execute(
            select(TimeOff).where(*conditions).order_by(TimeOff.start_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_agency(
        self,
        agency_id: uuid.UUID,
        status: str | None = None,
    ) -> list[TimeOff]:
        conditions = [
            TimeOff.agency_id == agency_id,
            TimeOff.deleted_at.is_(None),
        ]
        if status is not None:
            conditions.append(TimeOff.status == status)
        result = await self.db.execute(
            select(TimeOff).where(*conditions).order_by(TimeOff.start_at.asc())
        )
        return list(result.scalars().all())

    async def create(self, data: dict) -> TimeOff:
        obj = TimeOff(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, obj: TimeOff, data: dict) -> TimeOff:
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.flush()
        return obj

    async def soft_delete(self, obj: TimeOff) -> None:
        obj.soft_delete()
        await self.db.flush()
